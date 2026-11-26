"""Dados para apresentação: "Empresa Teste" com viagens todos os dias até 10/12.

- Empresa: empresateste@gmail.com (senha em PRESENTATION_COMPANY_PASSWORD).
- Motorista: motoristateste@gmail.com e passageiro: teste@gmail.com (senha em PRESENTATION_PASSWORD).
  O motorista faz todas as viagens e o passageiro está em todas.
- Mais 9 passageiros e 2 motoristas fictícios (sem login), 2 veículos e um grupo com ida e volta diárias.
- Cada dia já nasce com todos os passageiros confirmados; no prazo (22h da véspera) o worker fecha o dia
  e calcula a rota, e no dia o motorista inicia (o início publica a rota).

As senhas nunca ficam no código: vêm do ambiente. Idempotente: rodar de novo só completa o que falta.
"""

import os
from datetime import date, time, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from modules.accounts.models import User
from modules.organizations.models import Company, Driver, Passenger
from modules.organizations.services.groups import assign_passenger_group
from modules.transport.services.calendar import generate_day
from modules.transport.services.configuration import (
    authorize_services,
    configure_group,
    configure_policy,
    configure_service,
    configure_vehicle,
)
from modules.transport.services.governance import review_company
from modules.uploads.models import Image
from shared.demo import make_cnpj, make_cpf

from .seed_showcase import DESTINATION, PASSENGERS, _avatar
from .seed_showcase import Command as ShowcaseCommand

LAST_DAY = date(2026, 12, 10)
FICTITIOUS_DOMAIN = 'apresentacao.nextrouter.invalid'

COMPANY_EMAIL = 'empresateste@gmail.com'
DRIVER_EMAIL = 'motoristateste@gmail.com'
PASSENGER_EMAIL = 'teste@gmail.com'

GARAGE = (
    'Garagem Empresa Teste',
    'Rua Dona Francisca',
    '4300',
    'Santo Antônio',
    'Joinville',
    '89218115',
    -26.2732,
    -48.8523,
)

VEHICLES = (
    ('TST1A23', 'van', 'Mercedes-Benz', 'Sprinter 416 Escolar', 2023, 16, 15, 'Branco', ['Ar-condicionado', 'Wi-Fi']),
    ('TST4B56', 'microbus', 'Volare', 'W9 Fly', 2022, 28, 26, 'Branco e laranja', ['Ar-condicionado', 'Acessível']),
)


class Command(ShowcaseCommand):
    help = 'Cria a Empresa Teste para apresentação, com viagens diárias até 10/12 (dados fictícios).'

    def handle(self, *args, **options):
        company_password = os.environ.get('PRESENTATION_COMPANY_PASSWORD', '')
        user_password = os.environ.get('PRESENTATION_PASSWORD', '')
        if not options['confirm_fictitious'] or len(company_password) < 6 or len(user_password) < 6:
            raise CommandError(
                'Use --confirm-fictitious e defina PRESENTATION_COMPANY_PASSWORD e PRESENTATION_PASSWORD (6+).'
            )
        with transaction.atomic():
            summary = self._seed_presentation(company_password, user_password)
        self.stdout.write(self.style.SUCCESS(summary))

    def _account(self, email, name, base_cpf, password=None, *, phone=''):
        """Conta com e-mail exato. Com senha, ela é (re)definida a cada execução; sem senha, não entra."""
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=None, name=name, cpf=make_cpf(base_cpf))
            if phone:
                user.phone = phone
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        current = user.profile_picture
        if current is None or not current.file or not current.file.storage.exists(current.file.name):
            slug = email.split('@')[0]
            user.profile_picture = Image.objects.create(
                description=f'Foto de {name}', file=ContentFile(_avatar(name), name=f'{slug}.png')
            )
            user.save(update_fields=['profile_picture'])
        return user

    def _driver(self, company, email, name, base_cpf, password=None, phone=''):
        user = self._account(email, name, base_cpf, password, phone=phone)
        profile, _ = Driver.objects.get_or_create(user=user)
        if profile.location_consent_at is None:
            profile.location_consent_at = timezone.now()
            profile.save(update_fields=['location_consent_at'])
        return self._member(company, profile, 'driver_id')

    def _seed_presentation(self, company_password, user_password):
        moderator = self._account(f'moderacao@{FICTITIOUS_DOMAIN}', 'Moderação da apresentação', '920000001')
        if not moderator.is_staff:
            moderator.is_staff = moderator.is_superuser = True
            moderator.save(update_fields=['is_staff', 'is_superuser'])

        owner = self._account(COMPANY_EMAIL, 'Empresa Teste', '920000002', company_password)
        company, _ = Company.objects.get_or_create(
            user=owner,
            defaults={
                'trade_name': 'Empresa Teste',
                'legal_name': 'Empresa Teste Transportes Escolares LTDA',
                'cnpj': make_cnpj('920000030001'),
            },
        )
        if not company.is_approved:
            review_company(actor_id=moderator.pk, company_id=company.pk, approve=True)

        garage = self._point(company, *GARAGE[:1], 'garage', *GARAGE[1:])
        campus = self._point(company, *DESTINATION[:1], 'destination', *DESTINATION[1:])

        driver = self._driver(company, DRIVER_EMAIL, 'Motorista Teste', '920000101', user_password, '47998220001')
        for index, name in enumerate(('Paulo Henrique Souza', 'Fernanda Lima Rocha'), start=2):
            self._driver(company, f'motorista{index}@{FICTITIOUS_DOMAIN}', name, f'92000010{index}')

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

        name = 'Empresa Teste — IFC Araquari'
        existing = company.route_groups.filter(name=name).first()
        group = configure_group(
            actor_id=company.user_id,
            company_id=company.pk,
            group_id=existing.pk if existing else None,
            name=name,
            destination_id=campus.pk,
        )
        # Janela de resposta aberta com antecedência: dá para confirmar todos os dias até 10/12 agora.
        configure_policy(
            actor_id=company.user_id,
            group_id=group.pk,
            opens_days_before=30,
            opens_time=time(6),
            normal_days_before=1,
            normal_time=time(22),
            extension_days_before=0,
            extension_time=time(5),
        )
        services = []
        for direction, clock in (('outbound', time(7, 30)), ('return', time(17, 30))):
            current = group.services.filter(direction=direction).first()
            services.append(
                configure_service(
                    actor_id=company.user_id,
                    group_id=group.pk,
                    service_id=current.pk if current else None,
                    name='Ida IFC' if direction == 'outbound' else 'Volta IFC',
                    direction=direction,
                    weekdays=127,  # todos os dias, inclusive fim de semana (apresentação)
                    target_time=clock,
                    valid_from=timezone.localdate(),
                    driver_membership_id=driver.pk,
                    vehicle_id=vehicles[0].pk,
                    planned_duration=timedelta(minutes=180),  # 10 casas entre Joinville e Araquari
                    turnaround_duration=timedelta(minutes=15),
                )
            )

        riders = [(PASSENGER_EMAIL, 'Passageiro Teste', *PASSENGERS[0][1:], user_password)]
        riders += [
            (f'passageiro{index}@{FICTITIOUS_DOMAIN}', person[0], *person[1:], None)
            for index, person in enumerate(PASSENGERS[1:10], start=2)
        ]
        for index, (email, person, neighborhood, lat, lng, password) in enumerate(riders, start=1):
            user = self._account(email, person, f'9200002{index:02d}', password)
            profile, _ = Passenger.objects.get_or_create(user=user)
            member = self._member(company, profile, 'passenger_id')
            city = 'Joinville' if 'Joinville' in neighborhood else 'Araquari'
            point = self._point(
                company,
                f'Casa de {person.split()[0]} (teste)',
                'passenger',
                'Rua da Apresentação',
                str(100 + index * 10),
                neighborhood.replace(' (Joinville)', ''),
                city,
                '89245000' if city == 'Araquari' else '89220000',
                lat,
                lng,
            )
            if not member.passenger_group_memberships.filter(ended_at__isnull=True).exists():
                participation = assign_passenger_group(
                    actor_id=company.user_id,
                    membership_id=member.pk,
                    route_group_id=group.pk,
                    transport_point_id=point.pk,
                )
                authorize_services(
                    actor_id=company.user_id,
                    group_membership_id=participation.pk,
                    service_ids=[service.pk for service in services],
                    habitual_outbound_id=services[0].pk,
                )

        day = timezone.localdate() + timedelta(days=1)
        days = 0
        while day <= LAST_DAY:
            generate_day(actor_id=company.user_id, group_id=group.pk, date=day)
            self._answer_day(group, day, services[0], services[1])
            day += timedelta(days=1)
            days += 1

        return (
            f'Apresentação pronta: Empresa Teste, {len(riders)} passageiros, 3 motoristas, {days} dias de viagem '
            f'(ida e volta) até {LAST_DAY:%d/%m}. Logins: {COMPANY_EMAIL}, {DRIVER_EMAIL}, {PASSENGER_EMAIL}.'
        )
