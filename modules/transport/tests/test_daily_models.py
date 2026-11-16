from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from modules.transport.models import (
    DailyChangeRequest,
    DailyResponse,
    ResponsePolicy,
    ServiceDay,
    ServiceDayEligibility,
)

from .helpers import DayModelTestCase


class CalendarModelTests(DayModelTestCase):
    def policy_data(self, **extra):
        return {
            'route_group': self.group,
            'opens_days_before': 1,
            'opens_time': '12:00',
            'normal_days_before': 1,
            'normal_time': '22:00',
            **extra,
        }

    def test_policy_accepts_optional_extension_across_midnight(self):
        ResponsePolicy.objects.create(**self.policy_data(extension_days_before=0, extension_time='06:00')).full_clean()

    def test_policy_rejects_reversed_windows_or_partial_extension(self):
        for extra in (
            {'opens_time': '23:00'},
            {'opens_days_before': 0},
            {'extension_time': '06:00'},
            {'extension_days_before': 0},
            {'extension_days_before': 1, 'extension_time': '21:00'},
        ):
            with self.subTest(extra=extra):
                self.assert_db_rejects(ResponsePolicy, **self.policy_data(**extra))

    def test_day_is_unique_and_keeps_cancellation_tombstone(self):
        self.day.canceled_at = self.now
        self.day.canceled_by = self.company.user
        self.day.cancellation_reason = 'Data cancelada.'
        self.day.save()
        self.day.full_clean()
        self.assert_db_rejects(
            ServiceDay,
            route_group=self.group,
            date=self.tomorrow,
            opens_at=self.day.opens_at,
            normal_deadline=self.day.normal_deadline,
        )

    def test_day_checks_deadlines_and_cancellation_audit_on_update(self):
        for changes in (
            {'normal_deadline': self.day.opens_at},
            {'extension_deadline': self.day.normal_deadline},
            {'revision': 0},
            {'canceled_at': self.now},
        ):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                ServiceDay.objects.filter(pk=self.day.pk).update(**changes)

    def test_eligibility_is_unique_and_validates_group_and_snapshot_ids(self):
        self.eligibility.full_clean()
        self.assert_db_rejects(
            ServiceDayEligibility,
            day=self.day,
            passenger=self.passenger,
            group_membership=self.participation,
        )
        for ids in ([1, 1], ['1'], [True], [0], {}):
            self.eligibility.authorized_service_ids = ids
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                self.eligibility.full_clean()

    def test_live_configuration_does_not_rewrite_frozen_day(self):
        self.participation.transport_point = self.other_point
        self.participation.save(update_fields=['transport_point'])
        self.eligibility.refresh_from_db()
        self.assertEqual(self.eligibility.point_snapshot, {'latitude': -26.3, 'longitude': -48.8})


class DemandModelTests(DayModelTestCase):
    def request_data(self, response, **extra):
        return {
            'response': response,
            'leg': 'return',
            'proposed_service': self.return_service,
            'expected_response_revision': response.revision,
            'requested_by': self.passenger.user,
            'created_at': self.now,
            'expires_at': self.day.extension_deadline,
            **extra,
        }

    def test_missing_response_differs_from_negative_response(self):
        self.assertFalse(DailyResponse.objects.filter(eligibility=self.eligibility).exists())
        response = DailyResponse.objects.create(eligibility=self.eligibility)
        response.full_clean()
        self.assertIsNone(response.outbound_service_id)
        self.assertIsNone(response.return_service_id)
        self.assertIsNotNone(response.answered_at)
        self.assert_db_rejects(DailyResponse, eligibility=self.eligibility)

    def test_response_has_independent_legs_and_requires_authorized_direction(self):
        response = DailyResponse(
            eligibility=self.eligibility,
            outbound_service=self.service,
            return_service=self.return_service,
        )
        response.full_clean()
        response.return_service = self.service
        with self.assertRaises(ValidationError):
            response.full_clean()
        response.return_service = None
        response.full_clean()

    def test_approval_is_not_application_and_does_not_change_response(self):
        response = DailyResponse.objects.create(eligibility=self.eligibility, outbound_service=self.service)
        request = DailyChangeRequest.objects.create(
            **self.request_data(
                response,
                status='approved',
                application='preparing',
                decided_by=self.company.user,
                decided_at=self.now,
            )
        )
        request.full_clean()
        response.refresh_from_db()
        self.assertIsNone(response.return_service_id)
        request.application = 'failed'
        request.save(update_fields=['application'])
        response.refresh_from_db()
        self.assertIsNone(response.return_service_id)

    def test_one_open_request_per_response_leg(self):
        response = DailyResponse.objects.create(eligibility=self.eligibility)
        DailyChangeRequest.objects.create(**self.request_data(response))
        self.assert_db_rejects(DailyChangeRequest, **self.request_data(response))
        DailyChangeRequest.objects.create(**self.request_data(response, leg='outbound', proposed_service=self.service))

    def test_decision_must_be_before_expiry_and_have_actor(self):
        response = DailyResponse.objects.create(eligibility=self.eligibility)
        for changes in (
            {'decided_at': self.day.extension_deadline, 'decided_by': self.company.user, 'status': 'approved'},
            {'status': 'approved'},
            {'status': 'expired'},
            {'decided_by': self.company.user, 'decided_at': self.now},
            {'decided_at': self.now},
            {'expires_at': self.now - timedelta(seconds=1)},
            {'status': 'invalid'},
            {'application': 'applied', 'applied_at': self.now},
        ):
            with self.subTest(changes=changes):
                self.assert_db_rejects(DailyChangeRequest, **self.request_data(response, **changes))

    def test_request_proposal_must_match_leg(self):
        response = DailyResponse.objects.create(eligibility=self.eligibility)
        with self.assertRaises(ValidationError):
            DailyChangeRequest(**self.request_data(response, proposed_service=self.service)).full_clean()
