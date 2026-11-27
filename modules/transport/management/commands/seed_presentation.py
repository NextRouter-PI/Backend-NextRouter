"""Dados para apresentação: "Empresa Teste" com viagens todos os dias até 10/12.

E-mails e senhas vêm do ambiente (nada de dado pessoal ou senha no código):
- PRESENTATION_COMPANY_EMAIL e PRESENTATION_COMPANY_PASSWORD: dono da empresa.
- PRESENTATION_DRIVER_EMAIL: motorista que faz todas as viagens (aceita "Nome <email>").
- PRESENTATION_PASSENGER_EMAILS: passageiros separados por vírgula (aceita "Nome <email>"), em todas as viagens.
- PRESENTATION_PASSWORD: senha do motorista e dos passageiros.

Idempotente e reconfigurável: rodar de novo troca o e-mail das contas já criadas (empresa e motorista),
cadastra os passageiros novos e tira da van quem saiu da lista (desiste das viagens e encerra o vínculo).
"""

import os
import re
from datetime import date, time, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from modules.accounts.models import User
from modules.organizations.models import Company, Driver, Passenger
from modules.organizations.services.groups import assign_passenger_group
from modules.organizations.services.memberships import end_membership
from modules.transport.models import DailyResponse, Travel
from modules.transport.services.calendar import generate_day
from modules.transport.services.configuration import (
    authorize_services,
    configure_group,
    configure_policy,
    configure_service,
    configure_vehicle,
)
from modules.transport.services.demand import withdraw_leg
from modules.transport.services.governance import review_company
from modules.transport.services.planning import calculate_travel
from modules.uploads.models import Image
from shared.demo import make_cnpj, make_cpf
from shared.exceptions import DomainError

from .seed_showcase import DESTINATION, PASSENGERS, _avatar
from .seed_showcase import Command as ShowcaseCommand

LAST_DAY = date(2026, 12, 10)
FICTITIOUS_DOMAIN = 'apresentacao.nextrouter.invalid'
TRADE_NAME = 'Empresa Teste'
# Conta criada na primeira versão deste comando: é renomeada para o e-mail configurado.
LEGACY_DRIVER_EMAIL = 'motoristateste@gmail.com'

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


def _parse_people(raw):
    """'Nome <email>' ou só 'email' -> [(nome, email)]; sem nome, ele sai do próprio e-mail."""
    people = []
    for chunk in (part.strip() for part in raw.split(',')):
        if not chunk:
            continue
        match = re.match(r'^(.*?)\s*<([^>]+)>$', chunk)
        name, email = (match.group(1).strip(), match.group(2).strip()) if match else ('', chunk)
        if not name:
            words = [w for w in re.split(r'[._\-+0-9]+', email.split('@')[0]) if w and w.lower() != 'ifc']
            name = ' '.join(w.capitalize() for w in words) or email
        people.append((name, email.lower()))
    return people


class Command(ShowcaseCommand):
    help = 'Cria/atualiza a Empresa Teste para apresentação, com viagens diárias até 10/12.'

    def handle(self, *args, **options):
        company_password = os.environ.get('PRESENTATION_COMPANY_PASSWORD', '')
        user_password = os.environ.get('PRESENTATION_PASSWORD', '')
        if not options['confirm_fictitious'] or len(company_password) < 6 or len(user_password) < 6:
            raise CommandError(
                'Use --confirm-fictitious e defina PRESENTATION_COMPANY_PASSWORD e PRESENTATION_PASSWORD (6+).'
            )
        company_email = (
            os.environ.get('PRESENTATION_COMPANY_EMAIL', '').strip().lower() or f'empresa@{FICTITIOUS_DOMAIN}'
        )
        driver = _parse_people(os.environ.get('PRESENTATION_DRIVER_EMAIL', '')) or [
            ('Motorista Teste', f'motorista@{FICTITIOUS_DOMAIN}')
        ]
        riders = _parse_people(os.environ.get('PRESENTATION_PASSENGER_EMAILS', '')) or [
            ('Passageiro Teste', f'passageiro@{FICTITIOUS_DOMAIN}')
        ]
        if len(riders) > len(PASSENGERS):
            raise CommandError(f'No máximo {len(PASSENGERS)} passageiros.')
        with transaction.atomic():
            summary = self._seed_presentation(company_email, company_password, driver[0], riders, user_password)
        self.stdout.write(self.style.SUCCESS(summary))

    def _account(self, email, name, base_cpf, password=None, *, phone='', legacy_email=None, rename=False):
        """Conta pelo e-mail; se não existir, reaproveita a antiga (legacy_email) trocando o e-mail."""
        user = User.objects.filter(email=email).first()
        if user is None and legacy_email:
            user = User.objects.filter(email=legacy_email).first()
            if user is not None:
                user.email = email
                if rename:
                    user.name = name
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
            slug = re.sub(r'[^a-z0-9]+', '-', email.split('@')[0])
            user.profile_picture = Image.objects.create(
                description=f'Foto de {user.name}', file=ContentFile(_avatar(user.name), name=f'{slug}.png')
            )
            user.save(update_fields=['profile_picture'])
        return user

    def _driver(self, company, email, name, base_cpf, password=None, phone='', legacy_email=None):
        user = self._account(email, name, base_cpf, password, phone=phone, legacy_email=legacy_email, rename=True)
        profile, _ = Driver.objects.get_or_create(user=user)
        if profile.location_consent_at is None:
            profile.location_consent_at = timezone.now()
            profile.save(update_fields=['location_consent_at'])
        return self._member(company, profile, 'driver_id')

    def _remove_passenger(self, company, group_membership):
        """Tira da van: desiste de todos os trechos de hoje em diante e encerra o vínculo com a empresa."""
        membership = group_membership.membership
        user_id = membership.passenger.user_id
        touched = set()
        responses = DailyResponse.objects.filter(
            eligibility__passenger_id=membership.passenger_id,
            eligibility__day__route_group=group_membership.route_group,
            eligibility__day__date__gte=timezone.localdate(),
        ).select_related('eligibility')
        for response in responses:
            for leg in ('outbound', 'return'):
                if not response.has_active_choice(leg):
                    continue
                try:
                    with transaction.atomic():
                        withdraw_leg(actor_id=user_id, eligibility_id=response.eligibility_id, leg=leg)
                except DomainError:
                    continue
                touched.add(response.eligibility.day_id)
        # Dias já fechados: a viagem voltou a rascunho; pede o recálculo sem o passageiro.
        for travel in Travel.objects.filter(service_day_id__in=touched, status='scheduled', planning_status='draft'):
            if not travel.participations.filter(status='allocated').exists():
                continue
            try:
                with transaction.atomic():
                    calculate_travel(actor_id=company.user_id, travel_id=travel.pk, expected_revision=travel.revision)
            except DomainError:
                continue
        try:
            with transaction.atomic():
                end_membership(actor_id=company.user_id, membership_id=membership.pk, reason='Fora da apresentação')
        except DomainError:
            return 0
        return 1

    def _seed_presentation(self, company_email, company_password, driver_person, riders, user_password):
        moderator = self._account(f'moderacao@{FICTITIOUS_DOMAIN}', 'Moderação da apresentação', '920000001')
        if not moderator.is_staff:
            moderator.is_staff = moderator.is_superuser = True
            moderator.save(update_fields=['is_staff', 'is_superuser'])

        company = Company.objects.filter(trade_name=TRADE_NAME).select_related('user').first()
        owner = self._account(
            company_email,
            TRADE_NAME,
            '920000002',
            company_password,
            legacy_email=company.user.email if company else None,
        )
        if company is None:
            company = Company.objects.create(
                user=owner,
                trade_name=TRADE_NAME,
                legal_name='Empresa Teste Transportes Escolares LTDA',
                cnpj=make_cnpj('920000030001'),
            )
        if not company.is_approved:
            review_company(actor_id=moderator.pk, company_id=company.pk, approve=True)

        garage = self._point(company, *GARAGE[:1], 'garage', *GARAGE[1:])
        campus = self._point(company, *DESTINATION[:1], 'destination', *DESTINATION[1:])

        driver_name, driver_email = driver_person
        driver = self._driver(
            company, driver_email, driver_name, '920000101', user_password, '47998220001', LEGACY_DRIVER_EMAIL
        )
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
                    planned_duration=timedelta(minutes=180),  # casas entre Joinville e Araquari
                    turnaround_duration=timedelta(minutes=15),
                )
            )

        # Quem não está mais na lista sai da van.
        wanted = {email for _, email in riders}
        removed = 0
        for current in group.passenger_memberships.filter(ended_at__isnull=True).select_related(
            'membership__passenger__user', 'route_group'
        ):
            if current.membership.passenger.user.email.lower() not in wanted:
                removed += self._remove_passenger(company, current)

        for index, ((person, email), (_, neighborhood, lat, lng)) in enumerate(
            zip(riders, PASSENGERS, strict=False), start=1
        ):
            user = self._account(email, person, f'9200003{index:02d}', user_password)
            profile, _ = Passenger.objects.get_or_create(user=user)
            member = self._member(company, profile, 'passenger_id')
            city = 'Joinville' if 'Joinville' in neighborhood else 'Araquari'
            point = self._point(
                company,
                f'Casa de {person.split()[0]} (apresentação)',
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
            f'Apresentação pronta: {TRADE_NAME}, {len(riders)} passageiros (saíram {removed}), '
            f'{days} dias de viagem até {LAST_DAY:%d/%m}. Empresa: {owner.email}; motorista: {driver_email}.'
        )
