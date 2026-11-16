from unittest import mock

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from rest_framework.test import APIClient

from modules.organizations.models import OperationalPoint
from tests.helpers import create_company, create_operational_point, create_passenger, create_route_group, create_user


class OperationalPointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = create_company('point-company@example.com')
        cls.other_company = create_company('point-other-company@example.com')
        cls.creator = create_user('point-creator@example.com')
        cls.point = create_operational_point(cls.company, created_by=cls.creator)

    def test_complete_point_validates_and_preserves_author(self):
        self.point.full_clean()
        self.assertEqual(self.point.created_by, self.creator)
        self.assertIsNotNone(self.point.created_at)
        self.assertEqual(self.point.complement, '')

    def test_coordinates_accept_valid_boundaries(self):
        for latitude, longitude in ((-90, -180), (-90, 180), (90, -180), (90, 180), (0, 0)):
            with self.subTest(latitude=latitude, longitude=longitude):
                point = create_operational_point(self.company, latitude=latitude, longitude=longitude)
                point.full_clean()

    def test_database_rejects_missing_nonfinite_or_out_of_range_coordinates(self):
        for field, values in (
            ('latitude', (None, -90.1, 90.1, float('inf'), float('-inf'), float('nan'))),
            ('longitude', (None, -180.1, 180.1, float('inf'), float('-inf'), float('nan'))),
        ):
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(IntegrityError), transaction.atomic():
                    create_operational_point(self.company, **{field: value})

    def test_full_clean_reports_invalid_coordinates(self):
        for field in ('latitude', 'longitude'):
            original = getattr(self.point, field)
            for value in (float('nan'), float('inf'), 'invalid', None):
                with self.subTest(field=field, value=value):
                    setattr(self.point, field, value)
                    with self.assertRaises(ValidationError) as error:
                        self.point.full_clean()
                    self.assertIn(field, error.exception.message_dict)
            setattr(self.point, field, original)

    def test_database_rejects_empty_required_address_fields(self):
        for field in ('name', 'street', 'number', 'neighborhood', 'city', 'state', 'cep'):
            for value in ('', None):
                with self.subTest(field=field, value=value), self.assertRaises(IntegrityError), transaction.atomic():
                    create_operational_point(self.company, **{field: value})

    def test_full_clean_rejects_whitespace_only_address_fields(self):
        for field in ('name', 'street', 'number', 'neighborhood', 'city', 'state', 'cep'):
            original = getattr(self.point, field)
            setattr(self.point, field, ' ')
            with self.subTest(field=field), self.assertRaises(ValidationError) as error:
                self.point.full_clean()
            self.assertIn(field, error.exception.message_dict)
            setattr(self.point, field, original)

    def test_update_cannot_skip_coordinate_constraints(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            OperationalPoint.objects.filter(pk=self.point.pk).update(longitude=181)
        self.point.refresh_from_db()
        self.assertEqual(self.point.longitude, -48.8)

    def test_bulk_create_cannot_skip_coordinate_constraints(self):
        invalid = OperationalPoint(
            company=self.company,
            created_by=self.creator,
            name='Ponto',
            street='Rua',
            number='1',
            neighborhood='Centro',
            city='Cidade',
            state='SC',
            cep='89010-000',
            latitude=91,
            longitude=0,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            OperationalPoint.objects.bulk_create([invalid])

    def test_company_and_author_are_protected(self):
        for target in (self.company, self.creator):
            with self.subTest(model=type(target).__name__), self.assertRaises(ProtectedError):
                target.delete()

    def test_string_representation_omits_address_and_coordinates(self):
        self.assertEqual(str(self.point), f'Ponto #{self.point.pk} — empresa #{self.company.pk}')

    def test_creation_and_user_address_changes_do_not_geocode_or_modify_point(self):
        passenger = create_passenger('point-passenger@example.com')
        with (
            mock.patch('shared.geocoding.geocode_address') as geocode,
            mock.patch('modules.transport.osrm.optimize_coordinates') as osrm,
        ):
            point = create_operational_point(self.company)
            user = passenger.user
            user.street = 'Outro logradouro fictício'
            user.number = '200'
            user.latitude = 0
            user.longitude = 0
            user.save()
            point.refresh_from_db()
            self.assertEqual(point.street, 'Rua Fictícia')
            self.assertEqual(point.number, '100')
            self.assertEqual((point.latitude, point.longitude), (-26.3, -48.8))
            geocode.assert_not_called()
            osrm.assert_not_called()

    def test_new_points_are_not_public_api_resources(self):
        client = APIClient()
        client.force_authenticate(self.company.user)
        self.assertEqual(client.get('/api/operational-points/').status_code, 200)
        self.assertEqual(APIClient().get('/api/operational-points/').status_code, 401)


class GroupDestinationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = create_company('destination-company@example.com')
        cls.other_company = create_company('destination-other-company@example.com')
        cls.group = create_route_group(cls.company)
        cls.point = create_operational_point(cls.company)
        cls.other_point = create_operational_point(cls.other_company)

    def test_incomplete_group_can_exist_without_destination(self):
        self.assertIsNone(self.group.destination_id)
        self.group.full_clean()

    def test_destination_can_belong_to_same_company(self):
        self.group.destination = self.point
        self.group.full_clean()
        self.group.save(update_fields=['destination'])
        self.group.refresh_from_db()
        self.assertEqual(self.group.destination, self.point)

    def test_full_clean_rejects_destination_from_another_company(self):
        self.group.destination = self.other_point
        with self.assertRaises(ValidationError) as error:
            self.group.full_clean()
        self.assertIn('__all__', error.exception.message_dict)

    def test_full_clean_handles_missing_or_malformed_destination_ids(self):
        for value in (999999, 'invalid'):
            with self.subTest(destination=value):
                self.group.destination_id = value
                with self.assertRaises(ValidationError) as error:
                    self.group.full_clean()
                self.assertIn('destination', error.exception.message_dict)

    def test_destination_referenced_by_group_cannot_be_deleted(self):
        self.group.destination = self.point
        self.group.save(update_fields=['destination'])
        with self.assertRaises(ProtectedError):
            self.point.delete()

    def test_api_exposes_destination_to_owner_and_requires_explicit_id_input(self):
        client = APIClient()
        client.force_authenticate(self.company.user)
        url = f'/api/company-route-groups/{self.group.pk}/'
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('destination', response.data)
        response = client.patch(url, {'destination': self.point.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.group.refresh_from_db()
        self.assertIsNone(self.group.destination_id)
        response = client.patch(url, {'destination_id': self.point.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.group.refresh_from_db()
        self.assertEqual(self.group.destination_id, self.point.pk)
