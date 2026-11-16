from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APIClient

from modules.transport.models import (
    DailyChangeRequest,
    DailyResponse,
    ParticipationEvent,
    SeatReservation,
    Travel,
    TravelParticipation,
)
from tests.helpers import create_user

from .helpers import DayModelTestCase


class DatedTravelModelTests(DayModelTestCase):
    def travel_data(self, **extra):
        return {
            'company': self.company,
            'service_day': self.day,
            'service': self.service,
            'planned_start': self.now + timedelta(hours=3),
            'planned_end': self.now + timedelta(hours=4),
            **extra,
        }

    def test_draft_can_wait_for_driver_and_vehicle_without_shared_path(self):
        travel = Travel.objects.create(**self.travel_data())
        travel.full_clean()
        self.assertIsNone(travel.driver_id)
        self.assertNotIn('path', {field.name for field in travel._meta.fields})

    def test_only_one_travel_per_service_and_day(self):
        Travel.objects.create(**self.travel_data())
        self.assert_db_rejects(Travel, **self.travel_data())
        Travel.objects.create(**self.travel_data(service=self.return_service)).full_clean()

    def test_invalid_schedule_revisions_or_execution_are_rejected(self):
        for changes in (
            {'planned_end': self.now},
            {'planned_start': None},
            {'service': None},
            {'revision': 0},
            {'published_revision': 2},
            {'status': 'in_progress'},
            {'status': 'finished'},
            {'status': 'invalid'},
            {'planning_status': 'invalid'},
        ):
            with self.subTest(changes=changes):
                self.assert_db_rejects(Travel, **self.travel_data(**changes))

    def test_full_clean_checks_company(self):
        with self.assertRaises(ValidationError):
            Travel(**self.travel_data(company=self.other_company)).full_clean()

    def test_api_reads_dated_travel_but_legacy_confirmation_endpoint_is_removed(self):
        travel = Travel.objects.create(**self.travel_data())
        client = APIClient()
        client.force_authenticate(self.company.user)
        self.assertEqual(client.get(f'/api/travels/{travel.pk}/').status_code, 200)
        client.force_authenticate(self.passenger.user)
        self.assertEqual(client.post('/api/confirmations/', {'travel': travel.pk}, format='json').status_code, 404)

    def test_admin_cannot_change_new_travel(self):
        travel = Travel.objects.create(**self.travel_data())
        administrator = create_user('dated-travel-admin@example.com', is_staff=True, is_superuser=True)
        self.client.force_login(administrator)
        url = reverse('admin:router_travel_change', args=[travel.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {'status': 'finished'}).status_code, 403)


class ParticipationModelTests(DayModelTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.travel = Travel.objects.create(
            company=cls.company,
            service_day=cls.day,
            service=cls.service,
            planned_start=cls.now + timedelta(hours=3),
            planned_end=cls.now + timedelta(hours=4),
        )

    def participation_data(self, **extra):
        return {
            'travel': self.travel,
            'eligibility': self.eligibility,
            'leg': 'outbound',
            'allocated_at': self.now,
            **extra,
        }

    def test_each_execution_state_has_explicit_event_times(self):
        states = (
            ('allocated', {}),
            ('withdrawn', {'withdrawn_at': self.now}),
            ('no_show', {'no_show_at': self.now}),
            ('on_board', {'boarded_at': self.now}),
            ('dropped_off', {'boarded_at': self.now, 'dropped_off_at': self.now}),
        )
        for status, fields in states:
            participation = TravelParticipation.objects.create(**self.participation_data(status=status, **fields))
            participation.full_clean()
            participation.delete()

    def test_inconsistent_presence_cannot_be_written_in_bulk(self):
        for changes in (
            {'status': 'on_board'},
            {'status': 'dropped_off'},
            {'status': 'withdrawn', 'boarded_at': self.now},
            {'status': 'on_board', 'boarded_at': self.now - timedelta(seconds=1)},
            {'leg': 'invalid'},
        ):
            with self.subTest(changes=changes):
                self.assert_db_rejects(TravelParticipation, **self.participation_data(**changes))
        with self.assertRaises(IntegrityError), transaction.atomic():
            TravelParticipation.objects.bulk_create([
                TravelParticipation(**self.participation_data()),
                TravelParticipation(**self.participation_data()),
            ])

    def test_participation_requires_matching_leg(self):
        with self.assertRaises(ValidationError):
            TravelParticipation(**self.participation_data(leg='return')).full_clean()

    def test_correction_requires_reference_reason_and_unique_operation(self):
        participation = TravelParticipation.objects.create(**self.participation_data())
        event = ParticipationEvent.objects.create(
            participation=participation, kind='allocated', actor=self.company.user
        )
        self.assert_db_rejects(
            ParticipationEvent,
            participation=participation,
            kind='correction',
            actor=self.company.user,
        )
        correction = ParticipationEvent.objects.create(
            participation=participation,
            kind='correction',
            actor=self.company.user,
            corrects=event,
            reason='Correção auditada.',
        )
        correction.full_clean()
        self.assert_db_rejects(
            ParticipationEvent,
            participation=participation,
            kind='allocated',
            actor=self.company.user,
            operation_id=event.operation_id,
        )

    def test_reservation_is_separate_from_effective_allocation(self):
        participation = TravelParticipation.objects.create(**self.participation_data())
        response = DailyResponse.objects.create(eligibility=self.eligibility, outbound_service=self.service)
        request = DailyChangeRequest.objects.create(
            response=response,
            leg='return',
            proposed_service=self.return_service,
            expected_response_revision=1,
            requested_by=self.passenger.user,
            created_at=self.now,
            expires_at=self.day.extension_deadline,
            status='approved',
            decided_by=self.company.user,
            decided_at=self.now,
            application='preparing',
        )
        target = Travel.objects.create(
            company=self.company,
            service_day=self.day,
            service=self.return_service,
            planned_start=self.now + timedelta(hours=5),
            planned_end=self.now + timedelta(hours=6),
        )
        reservation = SeatReservation.objects.create(
            request=request,
            travel=target,
            expires_at=self.day.extension_deadline,
        )
        reservation.full_clean()
        self.assert_db_rejects(SeatReservation, request=request, travel=target, expires_at=self.day.extension_deadline)
        participation.refresh_from_db()
        self.assertEqual(participation.status, 'allocated')
        self.assertFalse(target.participations.exists())
