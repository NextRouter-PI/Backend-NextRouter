from datetime import timedelta

from django.db import IntegrityError, transaction

from modules.transport.models import DailyResponse, RecurringService, RouteSnapshot, Travel

from .helpers import DayModelTestCase


class Stage2SchemaTests(DayModelTestCase):
    def test_planning_duration_and_margin_have_database_checks_and_no_universal_default(self):
        self.service.refresh_from_db()
        self.assertIsNone(self.service.planned_duration)
        self.assertIsNone(self.service.turnaround_duration)
        for changes in (
            {'planned_duration': timedelta()},
            {'planned_duration': timedelta(seconds=-1)},
            {'turnaround_duration': timedelta(seconds=-1)},
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                RecurringService.objects.filter(pk=self.service.pk).update(**changes)
        RecurringService.objects.filter(pk=self.service.pk).update(
            planned_duration=timedelta(hours=1), turnaround_duration=timedelta()
        )
        self.service.refresh_from_db()
        self.service.full_clean()

    def test_placeholder_preserves_no_answer_instead_of_inventing_negative(self):
        response = DailyResponse.objects.create(eligibility=self.eligibility, answered_at=None)
        response.full_clean()
        self.assertIsNone(response.answered_at)
        self.assertIsNone(response.outbound_service_id)
        self.assertIsNone(response.return_service_id)

    def test_snapshot_candidate_period_is_paired_and_ordered(self):
        travel = Travel.objects.create(
            company=self.company,
            service_day=self.day,
            service=self.service,
            planned_start=self.now,
            planned_end=self.now + timedelta(hours=1),
        )
        snapshot = RouteSnapshot.objects.create(travel=travel, revision=2, base_revision=1)
        for changes in ({'planned_start': self.now}, {'planned_start': self.now, 'planned_end': self.now}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                RouteSnapshot.objects.filter(pk=snapshot.pk).update(**changes)
        RouteSnapshot.objects.filter(pk=snapshot.pk).update(
            planned_start=self.now, planned_end=self.now + timedelta(hours=1)
        )
        snapshot.refresh_from_db()
        snapshot.full_clean()
