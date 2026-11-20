import logging
import signal
from datetime import timedelta
from threading import Event, current_thread, main_thread
from time import monotonic

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections

from modules.organizations.models import Company
from modules.transport.services.automation import process_schedules
from modules.transport.services.common import DomainError
from modules.transport.services.jobs import claim_snapshot_job, process_snapshot_job
from modules.transport.services.maintenance import process_due

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Gera datas opt-in, fecha pendências e processa snapshots com limites e checkpoints persistentes.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--all-companies', action='store_true')
        parser.add_argument('--company-id', type=int)
        for name in (
            'lease-seconds',
            'max-attempts',
            'retry-seconds',
            'schedule-batch-size',
            'maintenance-batch-size',
            'job-batch-size',
        ):
            parser.add_argument(f'--{name}', type=int, required=True)
        parser.add_argument('--poll-seconds', type=int)

    def _process_company(self, company, options, stop):
        schedules = process_schedules(
            actor_id=company.user_id, company_id=company.pk, batch_size=options['schedule_batch_size']
        )
        outcomes = process_due(
            actor_id=company.user_id, company_id=company.pk, batch_size=options['maintenance_batch_size']
        )
        jobs = 0
        for _ in range(options['job_batch_size']):
            if stop.is_set():
                break
            job = claim_snapshot_job(
                company_id=company.pk,
                lease_duration=timedelta(seconds=options['lease_seconds']),
                max_attempts=options['max_attempts'],
            )
            if job is None:
                break
            process_snapshot_job(
                job_id=job.pk,
                claim_token=job.claim_token,
                max_attempts=options['max_attempts'],
                retry_delay=timedelta(seconds=options['retry_seconds']),
            )
            jobs += 1
        return len(schedules), len(outcomes), jobs

    def handle(self, *args, **options):
        all_companies = bool(options.get('all_companies'))
        company_id = options.get('company_id')
        if all_companies == (company_id is not None):
            raise CommandError('Informe exatamente um entre --company-id e --all-companies.')
        if (
            (company_id is not None and company_id <= 0)
            or options['lease_seconds'] <= 0
            or options['max_attempts'] <= 0
            or options['retry_seconds'] < 0
            or any(
                not 1 <= options[name] <= 1000
                for name in ('schedule_batch_size', 'maintenance_batch_size', 'job_batch_size')
            )
            or (not options['once'] and (options['poll_seconds'] is None or options['poll_seconds'] <= 0))
        ):
            raise CommandError('Informe limites positivos, lotes entre 1 e 1000; retry pode ser zero. Loop exige poll.')
        stop = Event()
        previous = {}
        if current_thread() is main_thread():
            for signum in (signal.SIGTERM, signal.SIGINT):
                previous[signum] = signal.signal(signum, lambda *_: stop.set())
        try:
            while not stop.is_set():
                close_old_connections()
                started = monotonic()
                total_schedules = 0
                total_outcomes = 0
                total_jobs = 0
                if all_companies:
                    companies = list(
                        Company.objects.filter(is_approved=True, is_rejected=False, user__is_active=True).order_by('pk')
                    )
                    for company in companies:
                        if stop.is_set():
                            break
                        try:
                            s_count, o_count, j_count = self._process_company(company, options, stop)
                            total_schedules += s_count
                            total_outcomes += o_count
                            total_jobs += j_count
                        except DomainError:
                            logger.error('worker_stopped reason=%s', 'domain')
                else:
                    company = Company.objects.filter(
                        pk=company_id, is_approved=True, is_rejected=False, user__is_active=True
                    ).first()
                    if company is None:
                        raise CommandError('Empresa aprovada/ativa não encontrada.')
                    total_schedules, total_outcomes, total_jobs = self._process_company(company, options, stop)
                logger.info(
                    'worker_cycle schedules=%d days=%d jobs=%d duration_ms=%d',
                    total_schedules,
                    total_outcomes,
                    total_jobs,
                    (monotonic() - started) * 1000,
                )
                close_old_connections()
                if options['once']:
                    return
                stop.wait(options['poll_seconds'])
        except (DatabaseError, DomainError) as exc:
            logger.error(
                'worker_stopped reason=%s', 'database_unavailable' if isinstance(exc, DatabaseError) else 'domain'
            )
            raise CommandError(
                'Worker interrompido; confira disponibilidade e configuração sem registrar dados privados.'
            ) from None
        finally:
            close_old_connections()
            for signum, handler in previous.items():
                signal.signal(signum, handler)
