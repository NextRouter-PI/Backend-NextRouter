from datetime import UTC, datetime, time, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import TransactionTestCase, override_settings

from modules.organizations.models import CompanyMembership, Driver, PassengerGroupMembership
from modules.transport.models import PassengerServiceAuthorization, RecurringService, ResponsePolicy, Vehicle
from modules.transport.services.calendar import generate_day
from modules.transport.services.common import DomainError
from modules.transport.services.demand import answer_day
from modules.transport.services.jobs import claim_snapshot_job, process_snapshot_job
from modules.transport.services.planning import close_day, publish_travel
from tests.helpers import create_company, create_operational_point, create_passenger, create_route_group, create_user


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ServiceTestCase(TransactionTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.now = datetime(2026, 11, 15, 12, tzinfo=UTC)
        clock = patch('django.utils.timezone.now', side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.company = create_company('operation-company@example.com')
        self.other = create_company('operation-other@example.com')
        self.garage = create_operational_point(self.company, name='Garagem', point_type='garage')
        self.common = create_operational_point(
            self.company, name='Destino comum', point_type='destination', latitude=-26.4
        )
        self.home = create_operational_point(
            self.company, name='Ponto do aluno', point_type='passenger', latitude=-26.35
        )
        self.group = create_route_group(self.company)
        self.group.destination = self.common
        self.group.save(update_fields=['destination'])
        self.driver = Driver.objects.create(user=create_user('operation-driver@example.com'))
        self.driver_membership = CompanyMembership.objects.create(
            company=self.company,
            driver=self.driver,
            status='active',
            requested_by=self.driver.user,
            created_at=self.now,
            reviewed_at=self.now,
            reviewed_by=self.company.user,
        )
        self.passenger = create_passenger('operation-passenger@example.com')
        self.membership = CompanyMembership.objects.create(
            company=self.company,
            passenger=self.passenger,
            status='active',
            requested_by=self.passenger.user,
            created_at=self.now,
            reviewed_at=self.now,
            reviewed_by=self.company.user,
        )
        self.group_member = PassengerGroupMembership.objects.create(
            membership=self.membership,
            route_group=self.group,
            transport_point=self.home,
            started_at=self.now,
            assigned_by=self.company.user,
        )
        self.vehicle = Vehicle.objects.create(
            company=self.company, garage_point=self.garage, plate='ABC1D23', capacity=2
        )
        self.outbound = self.make_service('outbound', time(8))
        self.returning = self.make_service('return', time(17))
        ResponsePolicy.objects.create(
            route_group=self.group,
            opens_days_before=1,
            opens_time=time(8),
            normal_days_before=1,
            normal_time=time(22),
            extension_days_before=0,
            extension_time=time(6),
        )
        for service in (self.outbound, self.returning):
            PassengerServiceAuthorization.objects.create(
                participation=self.group_member,
                service=service,
                direction=service.direction,
                is_habitual=service == self.outbound,
            )
        self.date = datetime(2026, 11, 16).date()
        self.day = generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        self.eligibility = self.day.eligibilities.get(passenger=self.passenger)
        for target in ('optimize_coordinates', 'route_coordinates'):
            provider = patch(f'modules.transport.services.routing.{target}', side_effect=self.route_result)
            provider.start()
            self.addCleanup(provider.stop)

    def make_service(self, direction, target):
        return RecurringService.objects.create(
            route_group=self.group,
            name=f'{direction}-{target}',
            direction=direction,
            weekdays=127,
            target_time=target,
            valid_from=self.now.date(),
            planned_duration=timedelta(hours=1),
            turnaround_duration=timedelta(minutes=10),
            driver_membership=self.driver_membership,
            vehicle=self.vehicle,
            origin=self.garage,
            destination=self.common if direction == 'outbound' else self.garage,
            created_by=self.company.user,
        )

    def route_result(self, coordinates, **kwargs):
        self.assertFalse(connection.in_atomic_block, 'Chamada OSRM ocorreu dentro de transação.')
        return {
            'order': list(range(len(coordinates))),
            'geometry': {'type': 'LineString', 'coordinates': coordinates},
            'distance_meters': 1000,
            'duration_seconds': 600 if len(coordinates) > 2 else 300,
        }

    def answer(self, *, outbound=True, returning=False):
        response = getattr(self.eligibility, 'response', None)
        # A relação reversa pode estar em cache; versão sempre relida do banco.
        from modules.transport.models import DailyResponse

        response = DailyResponse.objects.filter(eligibility=self.eligibility).first()
        return answer_day(
            actor_id=self.passenger.user_id,
            eligibility_id=self.eligibility.pk,
            outbound_service_id=self.outbound.pk if outbound else None,
            return_service_id=self.returning.pk if returning else None,
            expected_revision=response.revision if response else 0,
        )

    def close(self):
        self.now = self.day.normal_deadline
        close_day(actor_id=self.company.user_id, day_id=self.day.pk)

    def process_jobs(self, *, max_attempts=1):
        while (
            job := claim_snapshot_job(
                company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=max_attempts
            )
        ) is not None:
            process_snapshot_job(
                job_id=job.pk, claim_token=job.claim_token, max_attempts=max_attempts, retry_delay=timedelta(seconds=1)
            )

    def travel(self, service=None):
        return self.day.travels.get(service=service or self.outbound)

    def ready_travel(self, *, returning=False):
        self.answer(outbound=not returning, returning=returning)
        self.close()
        self.process_jobs()
        return self.travel(self.returning if returning else self.outbound)

    def publish(self, travel):
        travel.refresh_from_db()
        return publish_travel(actor_id=self.company.user_id, travel_id=travel.pk, expected_revision=travel.revision)

    def assert_domain(self, code, operation, **kwargs):
        with self.assertRaises(DomainError) as caught:
            operation(**kwargs)
        self.assertEqual(caught.exception.code, code)
