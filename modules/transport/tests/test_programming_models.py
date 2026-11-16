from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework.test import APIClient

from modules.transport.models import PassengerServiceAuthorization, RecurringService, RecurringServiceStop, Vehicle

from .helpers import Stage1ModelTestCase


class ProgrammingModelTests(Stage1ModelTestCase):
    def service_data(self, **extra):
        return {
            'route_group': self.group,
            'name': 'Serviço',
            'direction': 'outbound',
            'weekdays': 31,
            'target_time': '08:00',
            'valid_from': self.tomorrow,
            'created_by': self.company.user,
            **extra,
        }

    def test_independent_directions_validate_without_paired_hours(self):
        self.service.full_clean()
        self.return_service.full_clean()
        self.assertNotEqual(self.service.direction, self.return_service.direction)

    def test_database_rejects_invalid_weekdays_direction_and_validity(self):
        for extra in (
            {'weekdays': 0},
            {'weekdays': 128},
            {'direction': 'invalid'},
            {'valid_until': self.tomorrow - timedelta(days=1)},
        ):
            with self.subTest(extra=extra):
                self.assert_db_rejects(RecurringService, **self.service_data(**extra))

    def test_service_can_be_incomplete_but_cannot_cross_companies(self):
        RecurringService(**self.service_data()).full_clean()
        for field in ('origin', 'destination'):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RecurringService(**self.service_data(**{field: self.other_point})).full_clean()

    def test_passenger_membership_cannot_designate_habitual_driver(self):
        with self.assertRaises(ValidationError):
            RecurringService(**self.service_data(driver_membership=self.membership)).full_clean()

    def test_one_habitual_outbound_and_multiple_authorized_returns(self):
        PassengerServiceAuthorization.objects.create(
            participation=self.participation,
            service=self.service,
            direction='outbound',
            is_habitual=True,
        ).full_clean()
        PassengerServiceAuthorization.objects.create(
            participation=self.participation,
            service=self.return_service,
            direction='return',
        ).full_clean()
        second = RecurringService.objects.create(**self.service_data(name='Outra ida'))
        self.assert_db_rejects(
            PassengerServiceAuthorization,
            participation=self.participation,
            service=second,
            direction='outbound',
            is_habitual=True,
        )
        self.assert_db_rejects(
            PassengerServiceAuthorization,
            participation=self.participation,
            service=self.return_service,
            direction='return',
            is_habitual=True,
        )

    def test_authorization_validates_group_and_direction(self):
        service = RecurringService.objects.create(**self.service_data(route_group=self.other_group))
        for target, direction in ((service, 'outbound'), (self.service, 'return')):
            with self.subTest(service=target.pk), self.assertRaises(ValidationError):
                PassengerServiceAuthorization(
                    participation=self.participation,
                    service=target,
                    direction=direction,
                ).full_clean()

    def test_stops_have_positive_unique_order_and_same_company(self):
        stop = RecurringServiceStop.objects.create(service=self.service, point=self.point, position=1)
        stop.full_clean()
        for point, position in ((self.point, 2), (self.other_point, 1), (self.other_point, 0)):
            self.assert_db_rejects(RecurringServiceStop, service=self.service, point=point, position=position)
        with self.assertRaises(ValidationError):
            RecurringServiceStop(service=self.service, point=self.other_point, position=2).full_clean()

    def test_referenced_configuration_is_protected(self):
        PassengerServiceAuthorization.objects.create(
            participation=self.participation,
            service=self.service,
            direction='outbound',
        )
        with self.assertRaises(ProtectedError):
            self.service.delete()


class FleetModelTests(Stage1ModelTestCase):
    def test_company_owned_vehicle_needs_capacity_and_no_group(self):
        self.vehicle.full_clean()
        for extra in ({'capacity': None}, {'capacity': 0}, {'route_group': self.group}):
            self.assert_db_rejects(Vehicle, company=self.company, plate='XYZ1A23', **extra)
        self.assert_db_rejects(Vehicle, plate='XYZ1A23')

    def test_legacy_ownership_still_loads(self):
        legacy = Vehicle.objects.create(route_group=self.group, plate='LEG1A23')
        legacy.full_clean()

    def test_garage_cannot_belong_to_another_company(self):
        self.vehicle.garage_point = self.other_point
        with self.assertRaises(ValidationError):
            self.vehicle.full_clean()

    def test_bulk_updates_cannot_remove_company_vehicle_capacity(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vehicle.objects.filter(pk=self.vehicle.pk).update(capacity=None)

    def test_api_writes_company_vehicle_through_configuration_service(self):
        client = APIClient()
        client.force_authenticate(self.company.user)
        response = client.patch(f'/api/vehicles/{self.vehicle.pk}/', {'plate': 'BAD1A23'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
