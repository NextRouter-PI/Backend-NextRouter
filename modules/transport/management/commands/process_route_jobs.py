import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from modules.transport.models import RouteOptimizationJob
from modules.transport.optimization import claim_job, process_optimization
from modules.transport.osrm import OSRMError
from shared.geocoding import GeocodingError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Processa rotas pendentes fora das requisições HTTP.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        while True:
            job = claim_job()
            if job:
                try:
                    process_optimization(job)
                except (OSRMError, GeocodingError) as exc:
                    self._retry(job, str(exc))
                except Exception as exc:
                    logger.error('route_job_failed job_id=%s error_type=%s', job.pk, type(exc).__name__)
                    self._retry(job, 'Falha ao processar a rota. Tente novamente.')
            if options['once']:
                return
            if not job:
                time.sleep(2)

    def _retry(self, job, message):
        final = job.attempts >= 3
        RouteOptimizationJob.objects.filter(pk=job.pk, status=RouteOptimizationJob.Status.RUNNING).update(
            status=RouteOptimizationJob.Status.FAILED if final else RouteOptimizationJob.Status.PENDING,
            error=message,
            passenger_ids=[] if final else job.passenger_ids,
            start={} if final else job.start,
            end={} if final else job.end,
            available_at=timezone.now() + timedelta(seconds=2**job.attempts * 5),
        )
        logger.warning('route_job_retry job_id=%s attempts=%s final=%s', job.pk, job.attempts, final)
