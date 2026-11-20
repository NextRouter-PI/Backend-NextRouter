import os
from datetime import time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

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
from shared.demo import make_cnpj as make_cnpj
from shared.demo import make_cpf as make_cpf


class Command(BaseCommand):
    help = 'Cria fixture fictícia no domínio datado, somente em desenvolvimento e por confirmação explícita.'

    def add_arguments(self, parser):
        parser.add_argument('--confirm-fictitious', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get('DEMO_PASSWORD', '')
        if not settings.DEBUG or not options['confirm_fictitious'] or not password:
            raise CommandError('Use apenas em dev, --confirm-fictitious e DEMO_PASSWORD no ambiente. Sem reset.')

        def user(role, base, **values):
            found = User.objects.filter(email=f'{role}@fixture.example.invalid').first()
            return found or User.objects.create_user(
                email=f'{role}@fixture.example.invalid',
                password=password,
                name=f'Fixture {role}',
                cpf=make_cpf(base),
                **values,
            )

        moderator = user('moderator', '900000001', is_staff=True, is_superuser=True)
        company, _ = Company.objects.get_or_create(
            user=user('company', '900000002'),
            defaults={
                'trade_name': 'Empresa fictícia',
                'legal_name': 'Empresa fictícia LTDA',
                'cnpj': make_cnpj('900000010001'),
            },
        )
        review_company(actor_id=moderator.pk, company_id=company.pk, approve=True)
        driver, _ = Driver.objects.get_or_create(user=user('driver', '900000003'))
        passenger, _ = Passenger.objects.get_or_create(user=user('passenger', '900000004'))
        members = []
        for profile, field in ((driver, 'driver_id'), (passenger, 'passenger_id')):
            member = company.memberships.filter(**{field: profile.pk}, status='active').first()
            member = member or request_membership(
                actor_id=profile.user_id, company_id=company.pk, **{field: profile.pk}
            )
            members.append(approve_membership(actor_id=company.user_id, membership_id=member.pk))
        points = []
        point_specs = (
            ('Garagem fictícia', 'garage'),
            ('Destino fictício', 'destination'),
            ('Ponto fictício', 'passenger'),
        )
        for index, (name, point_type) in enumerate(point_specs):
            existing = company.operational_points.filter(name=name).first()
            points.append(
                configure_point(
                    actor_id=company.user_id,
                    company_id=company.pk,
                    point_id=existing.pk if existing else None,
                    name=name,
                    point_type=point_type,
                    street='Rua Fictícia',
                    number=str(index + 1),
                    neighborhood='Bairro fictício',
                    city='Cidade fictícia',
                    state='SC',
                    cep='89010000',
                    latitude=-26.3 - index / 100,
                    longitude=-48.8,
                )
            )
        existing = company.route_groups.filter(name='Grupo fictício').first()
        group = configure_group(
            actor_id=company.user_id,
            company_id=company.pk,
            group_id=existing.pk if existing else None,
            name='Grupo fictício',
            destination_id=points[1].pk,
        )
        vehicle = company.fleet.filter(plate='FIC1A23').first()
        vehicle = configure_vehicle(
            actor_id=company.user_id,
            company_id=company.pk,
            vehicle_id=vehicle.pk if vehicle else None,
            plate='FIC1A23',
            capacity=2,
            garage_point_id=points[0].pk,
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
        services = []
        for direction, clock in (('outbound', time(8)), ('return', time(17))):
            existing = group.services.filter(direction=direction).first()
            services.append(
                configure_service(
                    actor_id=company.user_id,
                    group_id=group.pk,
                    service_id=existing.pk if existing else None,
                    name=f'Fixture {direction}',
                    direction=direction,
                    weekdays=127,
                    target_time=clock,
                    valid_from=timezone.localdate(),
                    driver_membership_id=members[0].pk,
                    vehicle_id=vehicle.pk,
                    planned_duration=timedelta(hours=1),
                    turnaround_duration=timedelta(minutes=10),
                )
            )
        participation = assign_passenger_group(
            actor_id=company.user_id,
            membership_id=members[1].pk,
            route_group_id=group.pk,
            transport_point_id=points[2].pk,
        )
        authorize_services(
            actor_id=company.user_id,
            group_membership_id=participation.pk,
            service_ids=[service.pk for service in services],
            habitual_outbound_id=services[0].pk,
        )
        generate_day(actor_id=company.user_id, group_id=group.pk, date=timezone.localdate() + timedelta(days=1))
        self.stdout.write(self.style.SUCCESS('Fixture datada preparada. Credenciais não são exibidas.'))
