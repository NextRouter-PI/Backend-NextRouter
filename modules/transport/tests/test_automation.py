import signal
from datetime import timedelta
from threading import Event
from unittest.mock import patch

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from modules.transport.models import AutomationSchedule, RouteOptimizationJob
from modules.transport.services.automation import configure_automation, process_schedules
from modules.transport.services.calendar import generate_day
from modules.transport.services.common import DomainError
from modules.transport.services.execution import cancel_date
from modules.transport.services.jobs import claim_snapshot_job
from modules.transport.services.maintenance import process_due
from modules.transport.services.planning import calculate_travel, close_day

from .service_helpers import ServiceTestCase


class AutomationTests(ServiceTestCase):
    def configure(self, **extra):
        return configure_automation(**{
            'actor_id': self.company.user_id,
            'group_id': self.group.pk,
            'enabled': True,
            'horizon_days': 3,
            'batch_size': 1,
            'interval_seconds': 3600,
            'next_run_at': self.now,
            'expected_revision': 0,
            **extra,
        })

    def tick(self, **extra):
        return process_schedules(**{
            'actor_id': self.company.user_id,
            'company_id': self.company.pk,
            'batch_size': 1,
            **extra,
        })

    def test_opt_in_requires_all_policy_values_and_owner_with_current_revision(self):
        self.assertEqual(self.tick(), [])
        self.assert_domain('permission_denied', self.configure, actor_id=self.other.user_id)
        for extra in (
            {'horizon_days': 0},
            {'horizon_days': 32},
            {'batch_size': 4},
            {'interval_seconds': 0},
            {'next_run_at': self.now.replace(tzinfo=None)},
            {'enabled': 1},
        ):
            self.assert_domain('invalid_automation', self.configure, **extra)
        schedule = self.configure(enabled=False)
        self.assertEqual(self.tick(), [])
        self.assertEqual(schedule.configured_by_id, self.company.user_id)
        self.assert_domain('stale_revision', self.configure)
        self.configure(enabled=True, expected_revision=1)
        schedule.refresh_from_db()
        self.assertEqual(schedule.revision, 2)
        configured_at = schedule.configured_at
        self.configure(expected_revision=2)
        schedule.refresh_from_db()
        self.assertEqual((schedule.revision, schedule.configured_at), (2, configured_at))

    def test_database_rejects_invalid_batches_unknown_errors_and_partial_cursors(self):
        schedule = self.configure()
        for values in (
            {'horizon_days': 32},
            {'batch_size': 0},
            {'batch_size': 4},
            {'interval_seconds': 0},
            {'last_error_code': 'private text'},
            {'cursor_date': self.date},
        ):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                AutomationSchedule.objects.filter(pk=schedule.pk).update(**values)

    def test_checkpoint_survives_restart_and_repeated_due_cycles_do_not_duplicate(self):
        schedule = self.configure()
        self.assertEqual(self.tick(), [{'status': 'partial', 'processed': 1}])
        schedule.refresh_from_db()
        self.assertEqual(schedule.cursor_date, timezone.localdate(self.now) + timedelta(days=1))
        # Chamadas distintas reconstroem todo o estado pelo banco, sem cursor em memória.
        self.assertEqual(self.tick(), [{'status': 'partial', 'processed': 1}])
        self.assertEqual(self.tick(), [{'status': 'completed', 'processed': 1}])
        schedule.refresh_from_db()
        self.assertIsNone(schedule.cursor_date)
        self.assertEqual(schedule.next_run_at, self.now + timedelta(hours=1))
        count = self.group.days.count()
        self.assertEqual(count, 3)
        self.assertEqual(self.tick(), [])
        self.now += timedelta(hours=1)
        for _ in range(3):
            self.tick()
        self.assertEqual(self.group.days.count(), count)

    def test_failed_or_interrupted_batch_does_not_advance_dates_or_checkpoint(self):
        schedule = self.configure(batch_size=2)
        original_count = self.group.days.count()
        real_generate = generate_day
        calls = 0

        def fail_second(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValidationError('Não persistir motivo ou endereço fictício')
            return real_generate(**kwargs)

        with patch('modules.transport.services.automation.generate_day', side_effect=fail_second):
            self.assertEqual(self.tick(), [{'status': 'blocked', 'processed': 0}])
        self.assertEqual(self.group.days.count(), original_count)
        schedule.refresh_from_db()
        self.assertIsNone(schedule.cursor_date)
        self.assertEqual(schedule.last_error_code, 'generation_blocked')
        self.assertEqual(self.tick(), [])
        self.now = schedule.next_run_at
        with (
            patch('modules.transport.services.automation.generate_day', side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.tick()
        schedule.refresh_from_db()
        self.assertEqual(schedule.last_error_code, 'generation_blocked')
        self.assertEqual(self.group.days.count(), original_count)
        self.assertEqual(self.tick(), [{'status': 'partial', 'processed': 2}])

    def test_late_resume_never_backfills_past_days(self):
        schedule = self.configure()
        self.tick()
        first_count = self.group.days.count()
        self.now += timedelta(days=5)
        self.assertEqual(self.tick(), [{'status': 'completed', 'processed': 0}])
        self.assertEqual(self.group.days.count(), first_count)
        schedule.refresh_from_db()
        self.assertIsNone(schedule.cursor_date)
        self.now = schedule.next_run_at
        self.tick()
        self.assertTrue(self.group.days.filter(date=timezone.localdate(self.now)).exists())

    def test_publication_and_canceled_day_are_preserved(self):
        travel = self.ready_travel()
        self.publish(travel)
        original_revision = travel.revision
        future_date = self.date + timedelta(days=1)
        cancel_date(actor_id=self.company.user_id, group_id=self.group.pk, date=future_date, reason='Fictício')
        self.configure(batch_size=3)
        self.tick()
        travel.refresh_from_db()
        self.assertEqual(travel.revision, original_revision)
        self.assertTrue(travel.service_day.travels.filter(published_revision__isnull=False).exists())
        self.assertIsNotNone(self.group.days.get(date=future_date).canceled_at)

    def test_api_configuration_and_status_are_company_only_and_strict(self):
        client = APIClient()
        client.force_authenticate(self.company.user)
        url = f'/api/company-route-groups/{self.group.pk}/'
        self.assertEqual(client.get(f'{url}automation-status/').status_code, 404)
        data = {
            'enabled': True,
            'horizon_days': 3,
            'batch_size': 1,
            'interval_seconds': 3600,
            'next_run_at': self.now.isoformat(),
            'expected_revision': 0,
        }
        result = client.post(f'{url}automation/', {**data, 'cursor_date': '2026-11-20'}, format='json')
        self.assertEqual(result.status_code, 400)
        self.assertEqual(client.post(f'{url}automation/', data, format='json').status_code, 200)
        status = client.get(f'{url}automation-status/')
        self.assertEqual(status.data['revision'], 1)
        self.assertEqual(status.data['batch_size'], 1)
        client.force_authenticate(self.other.user)
        self.assertEqual(client.get(f'{url}automation-status/').status_code, 404)
        self.assertEqual(client.post(f'{url}automation/', data, format='json').status_code, 404)
        model_admin = admin.site._registry[AutomationSchedule]
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))

    def test_maintenance_rotates_blocked_dates_with_bounded_work(self):
        other_day = generate_day(
            actor_id=self.company.user_id, group_id=self.group.pk, date=self.date + timedelta(days=1)
        )
        self.now = other_day.normal_deadline
        real_close = close_day

        def block_first(**kwargs):
            if kwargs['day_id'] == self.day.pk:
                raise DomainError('Motivo fictício privado', code='no_demand')
            return real_close(**kwargs)

        with patch('modules.transport.services.maintenance.close_day', side_effect=block_first):
            first = process_due(actor_id=self.company.user_id, company_id=self.company.pk, batch_size=1)
            second = process_due(actor_id=self.company.user_id, company_id=self.company.pk, batch_size=1)
        self.assertEqual(first, {self.day.pk: 'no_demand'})
        self.assertEqual(second, {other_day.pk: 'closed'})

    def test_claim_inspects_only_one_exhausted_candidate_per_call(self):
        self.answer()
        self.close()
        for _ in range(2):
            travel = self.travel()
            calculate_travel(actor_id=self.company.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        RouteOptimizationJob.objects.update(attempts=1)
        self.assertIsNone(
            claim_snapshot_job(company_id=self.company.pk, lease_duration=timedelta(seconds=30), max_attempts=1)
        )
        self.assertEqual(RouteOptimizationJob.objects.filter(status='failed').count(), 1)
        self.assertEqual(RouteOptimizationJob.objects.filter(status='pending').count(), 2)


class PersistentWorkerTests(ServiceTestCase):
    def run_worker(self, **extra):
        return call_command(
            'process_route_jobs',
            **{
                'once': True,
                'company_id': self.company.pk,
                'lease_seconds': 30,
                'max_attempts': 2,
                'retry_seconds': 5,
                'schedule_batch_size': 1,
                'maintenance_batch_size': 2,
                'job_batch_size': 1,
                **extra,
            },
        )

    def test_limits_are_required_and_signals_are_restored(self):
        before = signal.getsignal(signal.SIGTERM)
        for name, value in (('maintenance_batch_size', 0), ('job_batch_size', 1001), ('lease_seconds', 0)):
            with self.subTest(name=name), self.assertRaises(CommandError):
                self.run_worker(**{name: value})
        self.run_worker()
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)

    def test_loop_waits_even_with_work_and_stop_finishes_current_cycle(self):
        stop = Event()
        with (
            patch('modules.transport.management.commands.process_route_jobs.Event', return_value=stop),
            patch.object(stop, 'wait', side_effect=lambda *_: stop.set()) as wait,
            patch('modules.transport.management.commands.process_route_jobs.process_due', return_value={}) as due,
        ):
            self.run_worker(once=False, poll_seconds=1)
        wait.assert_called_once_with(1)
        due.assert_called_once()

    def test_company_is_revalidated_after_each_wait(self):
        stop = Event()

        def deactivate(*_):
            self.company.is_approved = False
            self.company.save(update_fields=['is_approved'])

        with (
            patch('modules.transport.management.commands.process_route_jobs.Event', return_value=stop),
            patch.object(stop, 'wait', side_effect=deactivate),
            self.assertRaises(CommandError),
        ):
            self.run_worker(once=False, poll_seconds=1)

    def test_database_failure_is_sanitized_without_raw_exception_in_logs(self):
        with (
            patch(
                'modules.transport.management.commands.process_route_jobs.process_due',
                side_effect=DatabaseError('SegredoFicticioNuncaLogar'),
            ),
            self.assertLogs('modules.transport.management.commands.process_route_jobs', level='ERROR') as captured,
            self.assertRaises(CommandError) as caught,
        ):
            self.run_worker()
        self.assertNotIn('SegredoFicticioNuncaLogar', str(caught.exception) + str(captured.output))

    def test_all_companies_mode_processes_multiple_approved_companies_and_rejects_ambiguous_scope(self):
        with self.assertRaises(CommandError):
            self.run_worker(all_companies=True)
        self.other.is_approved = True
        self.other.is_rejected = False
        self.other.save(update_fields=['is_approved', 'is_rejected'])
        seen_companies = []

        def track_due(*, actor_id, company_id, batch_size):
            seen_companies.append(company_id)
            return {}

        with (
            patch('modules.transport.management.commands.process_route_jobs.process_schedules', return_value=[]),
            patch('modules.transport.management.commands.process_route_jobs.process_due', side_effect=track_due),
            patch('modules.transport.management.commands.process_route_jobs.claim_snapshot_job', return_value=None),
        ):
            self.run_worker(company_id=None, all_companies=True)
        self.assertEqual(seen_companies, sorted([self.company.pk, self.other.pk]))
