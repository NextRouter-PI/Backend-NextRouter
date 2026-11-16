import time
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError

from modules.organizations.models import Company
from modules.transport.services.jobs import claim_snapshot_job, process_snapshot_job
from modules.transport.services.maintenance import process_due


class Command(BaseCommand):
    help = 'Processa jobs de snapshots por claim/lease; nunca processa Path legado.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--lease-seconds', type=int, required=True)
        parser.add_argument('--max-attempts', type=int, required=True)
        parser.add_argument('--retry-seconds', type=int, required=True)
        parser.add_argument('--poll-seconds', type=int)

    def handle(self, *args, **options):
        if (
            options['lease_seconds'] <= 0
            or options['max_attempts'] <= 0
            or options['retry_seconds'] < 0
            or (not options['once'] and (options['poll_seconds'] is None or options['poll_seconds'] <= 0))
        ):
            raise CommandError('Informe limites positivos; retry pode ser zero. Loop exige --poll-seconds.')
        company = Company.objects.filter(pk=options['company_id'], is_approved=True, user__is_active=True).first()
        if company is None:
            raise CommandError('Empresa aprovada/ativa não encontrada.')
        while True:
            process_due(actor_id=company.user_id, company_id=company.pk)
            job = claim_snapshot_job(
                company_id=company.pk,
                lease_duration=timedelta(seconds=options['lease_seconds']),
                max_attempts=options['max_attempts'],
            )
            if job:
                process_snapshot_job(
                    job_id=job.pk,
                    claim_token=job.claim_token,
                    max_attempts=options['max_attempts'],
                    retry_delay=timedelta(seconds=options['retry_seconds']),
                )
            if options['once']:
                return
            if not job:
                time.sleep(options['poll_seconds'])
