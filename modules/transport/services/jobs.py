import uuid
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from modules.transport.models import RouteOptimizationJob
from modules.transport.osrm import OSRMError

from .common import DomainError, get, lock_company, require
from .requests import apply_request, fail_application
from .routing import calculate_frozen, persist_stops


@transaction.atomic
def claim_snapshot_job(*, company_id, lease_duration, max_attempts):
    require(
        isinstance(lease_duration, timedelta)
        and lease_duration > timedelta()
        and type(max_attempts) is int
        and max_attempts > 0,
        'invalid_worker_limits',
        'Informe lease e limite de tentativas positivos.',
    )
    lock_company(company_id)
    now = timezone.now()
    jobs = (
        RouteOptimizationJob.objects
        .filter(snapshot__travel__company_id=company_id, available_at__lte=now)
        .filter(Q(status='pending') | Q(status='running', claim_expires_at__lte=now))
        .order_by('pk')
    )
    # Cada claim examina no máximo um candidato, inclusive quando esgota tentativas.
    job = jobs.select_for_update(skip_locked=True).first()
    if job:
        if job.attempts >= max_attempts:
            _terminal_failure(job, 'attempts_exhausted')
            return None
        job.status, job.claim_token, job.claim_expires_at = 'running', uuid.uuid4(), now + lease_duration
        job.attempts += 1
        job.save(update_fields=['status', 'claim_token', 'claim_expires_at', 'attempts', 'updated_at'])
        return job
    return None


def _terminal_failure(job, error):
    job.status, job.error, job.claim_token, job.claim_expires_at = 'failed', error, None, None
    job.save(update_fields=['status', 'error', 'claim_token', 'claim_expires_at', 'updated_at'])
    snapshot = job.snapshot
    if snapshot.state == 'pending':
        snapshot.state = 'failed'
        snapshot.save(update_fields=['state'])
    if snapshot.change_request_id and snapshot.change_request.application == 'preparing':
        fail_application(snapshot.change_request)
    elif (
        not snapshot.change_request_id
        and snapshot.travel.status == 'scheduled'
        and snapshot.travel.revision == job.input_revision
    ):
        snapshot.travel.planning_status = 'blocked'
        snapshot.travel.save(update_fields=['planning_status'])


def _owned(job, token):
    return job.status == 'running' and job.claim_token == token and job.claim_expires_at > timezone.now()


@transaction.atomic
def _complete(job_id, token, result):
    initial = get(RouteOptimizationJob.objects.filter(snapshot__isnull=False), pk=job_id)
    lock_company(initial.snapshot.travel.company_id)
    job = get(RouteOptimizationJob.objects.select_for_update(), pk=job_id)
    if not _owned(job, token):
        return False
    snapshot, travel = job.snapshot, job.snapshot.travel
    if (
        snapshot.state != 'pending'
        or travel.status != 'scheduled'
        or travel.service_day.canceled_at
        or travel.revision != job.input_revision
        or job.frozen_input != snapshot.input_data
    ):
        _terminal_failure(job, 'stale_input')
        return False
    snapshot.geometry, snapshot.distance_meters = result['geometry'], result['distance_meters']
    snapshot.duration_seconds, snapshot.calculated_at, snapshot.state = (
        result['duration_seconds'],
        timezone.now(),
        'ready',
    )
    service = snapshot.input_data['service']
    target = timezone.make_aware(datetime.combine(travel.service_day.date, time.fromisoformat(service['target_time'])))
    budget, side = timedelta(seconds=service['duration']), timedelta(seconds=result['side_duration'])
    snapshot.planned_start, snapshot.planned_end = (
        (target - budget, target + side) if service['direction'] == 'outbound' else (target - side, target + budget)
    )
    snapshot.full_clean()
    snapshot.save()
    persist_stops(snapshot, result['stops'])
    job.status, job.claim_token, job.claim_expires_at, job.error = 'done', None, None, ''
    job.save(update_fields=['status', 'claim_token', 'claim_expires_at', 'error', 'updated_at'])
    # Ida chega ao destino no horário-alvo; retorno inclui a aproximação antes da partida comum.
    if snapshot.change_request_id is None:
        travel.planned_start, travel.planned_end = snapshot.planned_start, snapshot.planned_end
        pending = travel.route_snapshots.filter(
            change_request__status='approved',
            change_request__application='preparing',
        ).exists()
        travel.current_snapshot = snapshot
        travel.planning_status = (
            'preparing' if pending else 'ready' if travel.driver_id and travel.vehicle_id else 'blocked'
        )
        travel.save(update_fields=['planned_start', 'planned_end', 'current_snapshot', 'planning_status'])
    else:
        request = snapshot.change_request
        if request.route_snapshots.exclude(state='ready').exists():
            return True
        try:
            with transaction.atomic():
                apply_request(actor_id=travel.company.user_id, request_id=request.pk)
        except DomainError:
            request.refresh_from_db()
            fail_application(request)
    return True


@transaction.atomic
def _failed(job_id, token, *, max_attempts, retry_delay):
    initial = get(RouteOptimizationJob.objects.filter(snapshot__isnull=False), pk=job_id)
    lock_company(initial.snapshot.travel.company_id)
    job = get(RouteOptimizationJob.objects.select_for_update(), pk=job_id)
    if not _owned(job, token):
        return False
    if job.attempts >= max_attempts:
        _terminal_failure(job, 'calculation_failed')
    else:
        job.status, job.claim_token, job.claim_expires_at = 'pending', None, None
        job.error, job.available_at = 'calculation_failed', timezone.now() + retry_delay
        job.save(update_fields=['status', 'claim_token', 'claim_expires_at', 'error', 'available_at', 'updated_at'])
    return False


def process_snapshot_job(*, job_id, claim_token, max_attempts, retry_delay):
    require(not connection.in_atomic_block, 'outside_transaction_required', 'Execute OSRM fora de transação.')
    require(
        type(max_attempts) is int
        and max_attempts > 0
        and isinstance(retry_delay, timedelta)
        and retry_delay >= timedelta(),
        'invalid_worker_limits',
        'Limites de retry inválidos.',
    )
    job = get(RouteOptimizationJob.objects.filter(snapshot__isnull=False), pk=job_id)
    if not _owned(job, claim_token):
        return False
    try:
        result = calculate_frozen(job.frozen_input)
        return _complete(job_id, claim_token, result)
    except (ValidationError, OSRMError):
        return _failed(job_id, claim_token, max_attempts=max_attempts, retry_delay=retry_delay)
