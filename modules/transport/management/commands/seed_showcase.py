"""Vitrine fictícia para apresentar o NextRouter (empresa, motoristas, passageiros, frota e rotas).

Diferente do seed_demo_data (só dev), pode rodar em produção para apresentações, mas apenas com
--confirm-fictitious e SHOWCASE_PASSWORD no ambiente. Todos os e-mails usam o domínio reservado
.invalid (nunca recebem mensagens), os CPFs/CNPJs são fictícios e nada existente é apagado.
Rodar de novo não duplica: reaproveita o que já existe pelo e-mail, placa e nome.
"""

import colorsys
import hashlib
import io
import os
from datetime import time, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image as PILImage
from PIL import ImageDraw

from modules.accounts.models import User
from modules.organizations.models import Company, Driver, Passenger
from modules.organizations.services.groups import assign_passenger_group
from modules.organizations.services.memberships import approve_membership, request_membership
from modules.transport.services.calendar import generate_day
from modules.transport.services.configuration import (
    authorize_services,
    configure_group,
    configure_point,
    configure_policy,
    configure_service,
    configure_vehicle,
)
from modules.transport.services.governance import review_company
from modules.uploads.models import Image
from shared.demo import make_cnpj, make_cpf

DOMAIN = 'vitrine.nextrouter.invalid'

DRIVERS = (
    ('Carlos Eduardo Ramos', '47998112201'),
    ('Mariana Souza Lima', '47998112202'),
    ('Roberto Alves Pereira', '47998112203'),
    ('Juliana Costa Martins', '47998112204'),
    ('Anderson Silva Rocha', '47998112205'),
)

# Nome, bairro e coordenada aproximada da casa (Araquari e Joinville, SC).
PASSENGERS = (
    ('Ana Clara Ferreira', 'Centro', -26.3711, -48.7215),
    ('Bruno Henrique Dias', 'Itinga', -26.3889, -48.7062),
    ('Camila Rodrigues', 'Porto Grande', -26.4012, -48.7341),
    ('Diego Santos Moreira', 'Corveta', -26.3524, -48.7488),
    ('Eduarda Lopes', 'Barra do Itapocu', -26.4223, -48.6905),
    ('Felipe Augusto Neves', 'Volta Redonda', -26.3398, -48.7602),
    ('Gabriela Nunes', 'Itaum (Joinville)', -26.3267, -48.8312),
    ('Henrique Barbosa', 'Floresta (Joinville)', -26.3302, -48.8452),
    ('Isabela Cardoso', 'Boehmerwald (Joinville)', -26.3488, -48.8396),
    ('João Pedro Teixeira', 'Paranaguamirim (Joinville)', -26.3605, -48.7934),
    ('Larissa Monteiro', 'Ulysses Guimarães (Joinville)', -26.3442, -48.8021),
    ('Matheus Carvalho', 'Jarivatuba (Joinville)', -26.3379, -48.8198),
    ('Natália Ribeiro', 'Fátima (Joinville)', -26.3193, -48.8274),
    ('Otávio Pires Gomes', 'Guanabara (Joinville)', -26.3156, -48.8358),
)

VEHICLES = (
    # placa, tipo, marca, modelo, ano, assentos, capacidade, cor, características
    (
        'RTC1A01',
        'van',
        'Mercedes-Benz',
        'Sprinter 416 Escolar',
        2022,
        16,
        15,
        'Branco',
        ['Ar-condicionado', 'Cinto de três pontos'],
    ),
    ('RTC1A02', 'van', 'Renault', 'Master Executiva', 2021, 16, 15, 'Branco', ['Ar-condicionado', 'Wi-Fi']),
    ('RTC2B03', 'microbus', 'Volare', 'W9 Fly', 2023, 28, 26, 'Branco e laranja', ['Ar-condicionado', 'Acessível']),
    ('RTC3C04', 'bus', 'Marcopolo', 'Torino', 2020, 44, 42, 'Branco e laranja', ['Ar-condicionado', 'Bagageiro']),
)

GARAGE = (
    'Garagem Rota Certa',
    'Rua Dona Francisca',
    '4200',
    'Santo Antônio',
    'Joinville',
    '89218115',
    -26.2732,
    -48.8523,
)
DESTINATION = (
    'IFC Campus Araquari',
    'Rodovia BR-280, km 27',
    's/n',
    'Colégio Agrícola',
    'Araquari',
    '89245000',
    -26.3976,
    -48.7203,
)

PALETTE = ((236, 131, 20), (37, 99, 235), (22, 163, 74), (147, 51, 234), (220, 38, 38), (8, 145, 178), (202, 138, 4))


def _avatar(name):
    """Foto de perfil ilustrada: fundo em degradê e um busto estilizado com as iniciais."""
    seed = int(hashlib.sha256(name.encode()).hexdigest(), 16)
    base = PALETTE[seed % len(PALETTE)]
    h, light, sat = colorsys.rgb_to_hls(*(c / 255 for c in base))
    darker = tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, max(0, light - 0.18), sat))
    size = 384
    img = PILImage.new('RGB', (size, size), base)
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        draw.line([(0, y), (size, y)], fill=tuple(round(base[i] * (1 - t) + darker[i] * t) for i in range(3)))
    skin = ((241, 194, 160), (224, 172, 132), (198, 140, 101), (141, 85, 54))[seed // 7 % 4]
    hair = ((40, 28, 20), (88, 54, 30), (20, 20, 20), (150, 100, 50))[seed // 11 % 4]
    shirt = (255, 255, 255) if seed % 2 else (28, 28, 31)
    draw.ellipse((72, 250, 312, 470), fill=shirt)
    draw.rectangle((168, 210, 216, 270), fill=skin)
    draw.ellipse((120, 92, 264, 246), fill=skin)
    draw.chord((112, 78, 272, 214), 180, 360, fill=hair)
    for x in (165, 219):
        draw.ellipse((x - 7, 160, x + 7, 174), fill=(40, 30, 25))
    draw.arc((172, 186, 212, 214), 20, 160, fill=(150, 70, 60), width=4)
    out = io.BytesIO()
    img.save(out, format='PNG', optimize=True)
    return out.getvalue()


class Command(BaseCommand):
    help = 'Cria a vitrine fictícia do NextRouter (pode rodar em produção com confirmação explícita).'

    def add_arguments(self, parser):
        parser.add_argument('--confirm-fictitious', action='store_true')

    def handle(self, *args, **options):
        password = os.environ.get('SHOWCASE_PASSWORD', '')
        if not options['confirm_fictitious'] or len(password) < 10:
            raise CommandError('Use --confirm-fictitious e SHOWCASE_PASSWORD (10+ caracteres) no ambiente.')
        with transaction.atomic():
            summary = self._seed(password)
        self.stdout.write(self.style.SUCCESS(summary))

    def _user(self, slug, name, base_cpf, password, *, phone='', photo=True, usable=True):
        email = f'{slug}@{DOMAIN}'
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=password, name=name, cpf=make_cpf(base_cpf))
            if not usable:
                user.set_unusable_password()
            if phone:
                user.phone = phone
            user.save()
        if photo and user.profile_picture_id is None:
            picture = Image.objects.create(
                description=f'Foto de {name}', file=ContentFile(_avatar(name), name=f'{slug}.png')
            )
            user.profile_picture = picture
            user.save(update_fields=['profile_picture'])
        return user

    def _point(self, company, name, point_type, street, number, neighborhood, city, cep, lat, lng):
        existing = company.operational_points.filter(name=name).first()
        return configure_point(
            actor_id=company.user_id,
            company_id=company.pk,
            point_id=existing.pk if existing else None,
            name=name,
            point_type=point_type,
            street=street,
            number=number,
            neighborhood=neighborhood,
            city=city,
            state='SC',
            cep=cep,
            latitude=lat,
            longitude=lng,
        )

    def _member(self, company, profile, field):
        member = company.memberships.filter(**{field: profile.pk}, status='active').first()
        if member:
            return member
        member = request_membership(actor_id=profile.user_id, company_id=company.pk, **{field: profile.pk})
        return approve_membership(actor_id=company.user_id, membership_id=member.pk)

    def _seed(self, password):
        # Moderador técnico só para aprovar o cadastro; não consegue entrar (senha inutilizável).
        moderator = self._user('moderacao', 'Moderação da vitrine', '910000001', password, photo=False, usable=False)
        if not moderator.is_staff:
            moderator.is_staff = moderator.is_superuser = True
            moderator.save(update_fields=['is_staff', 'is_superuser'])

        owner = self._user('empresa', 'Rota Certa Transportes', '910000002', password)
        company, _ = Company.objects.get_or_create(
            user=owner,
            defaults={
                'trade_name': 'Rota Certa Transportes',
                'legal_name': 'Rota Certa Transportes Escolares LTDA',
                'cnpj': make_cnpj('910000020001'),
            },
        )
        if not company.is_approved:
            review_company(actor_id=moderator.pk, company_id=company.pk, approve=True)

        garage = self._point(company, *GARAGE[:1], 'garage', *GARAGE[1:])
        campus = self._point(company, *DESTINATION[:1], 'destination', *DESTINATION[1:])

        drivers = []
        for index, (name, phone) in enumerate(DRIVERS, start=1):
            user = self._user(f'motorista{index}', name, f'91000010{index}', password, phone=phone)
            profile, _ = Driver.objects.get_or_create(user=user)
            if profile.location_consent_at is None:
                profile.location_consent_at = timezone.now()
                profile.save(update_fields=['location_consent_at'])
            drivers.append(self._member(company, profile, 'driver_id'))

        vehicles = []
        for plate, kind, brand, model, year, seats, capacity, color, features in VEHICLES:
            existing = company.fleet.filter(plate=plate).first()
            vehicles.append(
                configure_vehicle(
                    actor_id=company.user_id,
                    company_id=company.pk,
                    vehicle_id=existing.pk if existing else None,
                    plate=plate,
                    vehicle_type=kind,
                    brand=brand,
                    model=model,
                    year=year,
                    seats=seats,
                    capacity=capacity,
                    color=color,
                    features=features,
                    garage_point_id=garage.pk,
                )
            )

        groups = []
        for name, outbound, back in (
            ('IFC Araquari — Manhã', time(7, 30), time(12, 10)),
            ('IFC Araquari — Tarde', time(13, 15), time(18, 0)),
        ):
            existing = company.route_groups.filter(name=name).first()
            group = configure_group(
                actor_id=company.user_id,
                company_id=company.pk,
                group_id=existing.pk if existing else None,
                name=name,
                destination_id=campus.pk,
            )
            configure_policy(
                actor_id=company.user_id,
                group_id=group.pk,
                opens_days_before=1,
                opens_time=time(8),
                normal_days_before=1,
                normal_time=time(22),
                extension_days_before=0,
                extension_time=time(6),
            )
            groups.append((group, outbound, back))

        services_by_group = []
        for index, (group, outbound, back) in enumerate(groups):
            services = []
            for direction, clock, offset in (('outbound', outbound, 0), ('return', back, 1)):
                existing = group.services.filter(direction=direction).first()
                services.append(
                    configure_service(
                        actor_id=company.user_id,
                        group_id=group.pk,
                        service_id=existing.pk if existing else None,
                        name=f'{"Ida" if direction == "outbound" else "Volta"} {group.name.split("— ")[-1]}',
                        direction=direction,
                        weekdays=31,  # segunda a sexta
                        target_time=clock,
                        valid_from=timezone.localdate(),
                        driver_membership_id=drivers[(index * 2 + offset) % len(drivers)].pk,
                        vehicle_id=vehicles[index * 2 + offset].pk,
                        planned_duration=timedelta(minutes=70),
                        turnaround_duration=timedelta(minutes=15),
                    )
                )
            services_by_group.append(services)

        for index, (name, neighborhood, lat, lng) in enumerate(PASSENGERS, start=1):
            user = self._user(f'passageiro{index}', name, f'9100002{index:02d}', password)
            profile, _ = Passenger.objects.get_or_create(user=user)
            member = self._member(company, profile, 'passenger_id')
            city = 'Joinville' if 'Joinville' in neighborhood else 'Araquari'
            point = self._point(
                company,
                f'Casa de {name.split()[0]}',
                'passenger',
                'Rua da Vitrine',
                str(100 + index * 10),
                neighborhood.replace(' (Joinville)', ''),
                city,
                '89245000' if city == 'Araquari' else '89220000',
                lat,
                lng,
            )
            group_index = index % 2
            group = groups[group_index][0]
            if not member.passenger_group_memberships.filter(ended_at__isnull=True).exists():
                participation = assign_passenger_group(
                    actor_id=company.user_id,
                    membership_id=member.pk,
                    route_group_id=group.pk,
                    transport_point_id=point.pk,
                )
                services = services_by_group[group_index]
                authorize_services(
                    actor_id=company.user_id,
                    group_membership_id=participation.pk,
                    service_ids=[service.pk for service in services],
                    habitual_outbound_id=services[0].pk,
                )

        today = timezone.localdate()
        for group, _outbound, _back in groups:
            for days in range(1, 4):
                day = today + timedelta(days=days)
                if day.weekday() < 5:
                    generate_day(actor_id=company.user_id, group_id=group.pk, date=day)

        return (
            f'Vitrine pronta: 1 empresa, {len(DRIVERS)} motoristas, {len(PASSENGERS)} passageiros, '
            f'{len(VEHICLES)} veículos, 2 grupos. Logins @{DOMAIN}; senha = SHOWCASE_PASSWORD.'
        )
