from datetime import timedelta
from unittest.mock import patch

from django.db import transaction

from modules.transport.osrm import OSRMError
from modules.transport.services.jobs import claim_snapshot_job, process_snapshot_job
from modules.transport.services.planning import calculate_travel

from .service_helpers import ServiceTestCase


class JobServiceTests(ServiceTestCase):
    def queue(self):
        self.answer()
        self.close()
        return claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=3)

    def process(self, job, **extra):
        return process_snapshot_job(**{
            'job_id': job.pk,
            'claim_token': job.claim_token,
            'max_attempts': 3,
            'retry_delay': timedelta(seconds=5),
            **extra,
        })

    def test_claim_prevents_duplicate_and_success_uses_only_frozen_points(self):
        job = self.queue()
        self.assertIsNone(
            claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=3)
        )
        self.home.latitude = -20
        self.home.save(update_fields=['latitude'])
        self.assertTrue(self.process(job))
        job.refresh_from_db()
        self.assertEqual(job.status, 'done')
        self.assertIsNone(job.claim_token)
        travel = self.travel()
        self.assertEqual(travel.planning_status, 'ready')
        self.assertEqual(travel.current_snapshot.input_data['participants'][0]['point']['latitude'], -26.35)
        self.assertFalse(self.process(job))

    def test_reclaimed_lease_rejects_late_previous_worker(self):
        first = self.queue()
        first_token = first.claim_token
        self.now += timedelta(minutes=6)
        second = claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=3)
        self.assertEqual(second.pk, first.pk)
        self.assertNotEqual(second.claim_token, first_token)
        self.assertFalse(
            process_snapshot_job(
                job_id=first.pk, claim_token=first_token, max_attempts=3, retry_delay=timedelta(seconds=5)
            )
        )
        self.assertTrue(self.process(second))

    def test_external_call_is_rejected_inside_atomic(self):
        job = self.queue()
        with transaction.atomic():
            self.assert_domain('outside_transaction_required', self.process, job=job)

    def test_retry_is_bounded_and_error_is_sanitized(self):
        job = self.queue()
        with patch(
            'modules.transport.services.jobs.calculate_frozen', side_effect=OSRMError('Não persistir endereço fictício')
        ):
            self.assertFalse(self.process(job, max_attempts=1))
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.error, 'calculation_failed')
        self.assertEqual(self.travel().planning_status, 'blocked')

    def test_timeout_exhaustion_is_observable_without_infinite_claims(self):
        job = self.queue()
        self.now += timedelta(minutes=6)
        self.assertIsNone(
            claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=1)
        )
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(job.error, 'attempts_exhausted')

    def test_obsolete_revision_cannot_overwrite_newer_calculation(self):
        old = self.queue()
        travel = self.travel()
        calculate_travel(actor_id=self.company.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        self.assertFalse(self.process(old))
        old.refresh_from_db()
        self.assertEqual(old.error, 'stale_input')
        newer = claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=3)
        self.assertTrue(self.process(newer))
        self.assertEqual(self.travel().current_snapshot_id, newer.snapshot_id)

    def test_retry_delay_prevents_immediate_reclaim(self):
        job = self.queue()
        with patch('modules.transport.services.jobs.calculate_frozen', side_effect=OSRMError('Falha fictícia')):
            self.assertFalse(self.process(job))
        self.assertIsNone(
            claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=3)
        )
        self.now += timedelta(seconds=5)
        retried = claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(minutes=5), max_attempts=3)
        self.assertEqual(retried.attempts, 2)

    def test_recalculation_does_not_accumulate_return_approach_in_schedule(self):
        travel = self.ready_travel(returning=True)
        first_start, first_end = travel.planned_start, travel.planned_end
        calculate_travel(actor_id=self.company.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        self.process_jobs()
        travel.refresh_from_db()
        self.assertEqual((travel.planned_start, travel.planned_end), (first_start, first_end))

    def test_calculation_without_driver_stays_blocked_instead_of_violating_ready_constraint(self):
        self.driver_membership.status = 'ended'
        self.driver_membership.ended_by = self.company.user
        self.driver_membership.ended_at = self.now
        self.driver_membership.save(update_fields=['status', 'ended_by', 'ended_at'])
        from modules.transport.services.calendar import generate_day

        generate_day(actor_id=self.company.user_id, group_id=self.group.pk, date=self.date)
        self.answer()
        self.close()
        self.process_jobs()
        travel = self.travel()
        self.assertIsNone(travel.driver_id)
        self.assertEqual(travel.planning_status, 'blocked')
        self.assertEqual(travel.current_snapshot.state, 'ready')
