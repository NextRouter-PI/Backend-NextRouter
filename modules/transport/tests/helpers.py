from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from modules.organizations.models import CompanyMembership, PassengerGroupMembership
from modules.transport.models import RecurringService, ServiceDay, ServiceDayEligibility, Vehicle
from tests.helpers import create_company, create_operational_point, create_passenger, create_route_group


class Stage1ModelTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = create_company('stage1-company@example.com')
        cls.other_company = create_company('stage1-other@example.com')
        cls.group = create_route_group(cls.company)
        cls.other_group = create_route_group(cls.other_company)
        cls.point = create_operational_point(cls.company)
        cls.other_point = create_operational_point(cls.other_company)
        cls.passenger = create_passenger('stage1-passenger@example.com')
        cls.now = timezone.now()
        cls.membership = CompanyMembership.objects.create(
            company=cls.company,
            passenger=cls.passenger,
            requested_by=cls.passenger.user,
            created_at=cls.now,
            status='active',
            reviewed_at=cls.now,
            reviewed_by=cls.company.user,
        )
        cls.participation = PassengerGroupMembership.objects.create(
            membership=cls.membership,
            route_group=cls.group,
            transport_point=cls.point,
            assigned_by=cls.company.user,
            started_at=cls.now,
        )
        cls.vehicle = Vehicle.objects.create(company=cls.company, plate='ABC1D23', capacity=10, garage_point=cls.point)
        cls.service = RecurringService.objects.create(
            route_group=cls.group,
            name='Ida',
            direction='outbound',
            weekdays=31,
            target_time='08:00',
            valid_from=timezone.localdate(),
            created_by=cls.company.user,
            vehicle=cls.vehicle,
            origin=cls.point,
            destination=cls.point,
        )
        cls.return_service = RecurringService.objects.create(
            route_group=cls.group,
            name='Retorno',
            direction='return',
            weekdays=31,
            target_time='17:00',
            valid_from=timezone.localdate(),
            created_by=cls.company.user,
        )
        cls.tomorrow = timezone.localdate() + timedelta(days=1)

    def assert_db_rejects(self, model, **data):
        with self.assertRaises(IntegrityError), transaction.atomic():
            model.objects.create(**data)


class DayModelTestCase(Stage1ModelTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.day = ServiceDay.objects.create(
            route_group=cls.group,
            date=cls.tomorrow,
            opens_at=cls.now - timedelta(hours=1),
            normal_deadline=cls.now + timedelta(hours=1),
            extension_deadline=cls.now + timedelta(hours=2),
            configuration_snapshot={'service_ids': [cls.service.pk, cls.return_service.pk]},
        )
        cls.eligibility = ServiceDayEligibility.objects.create(
            day=cls.day,
            passenger=cls.passenger,
            group_membership=cls.participation,
            authorized_service_ids=[cls.service.pk, cls.return_service.pk],
            point_snapshot={'latitude': -26.3, 'longitude': -48.8},
        )
