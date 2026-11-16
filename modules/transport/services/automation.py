"""Checkpoints transacionais de geração. Nunca mantém lock durante chamada externa."""

from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from modules.transport.models import AutomationSchedule, ResponsePolicy

from .calendar import generate_day
from .common import company_actor, get, lock_company, require
from .configuration import group_access

CONFIGURATION_FIELDS = ('enabled', 'horizon_days', 'batch_size', 'interval_seconds', 'next_run_at')


@transaction.atomic
def configure_automation(
    *, actor_id, group_id, enabled, horizon_days, batch_size, interval_seconds, next_run_at, expected_revision
):
    group = group_access(group_id, actor_id)
    require(type(enabled) is bool, 'invalid_automation', 'Informe habilitação explícita.')
    require(
        type(horizon_days) is int
        and 1 <= horizon_days <= 31
        and type(batch_size) is int
        and 1 <= batch_size <= horizon_days
        and type(interval_seconds) is int
        and 1 <= interval_seconds <= 2147483647
        and type(expected_revision) is int
        and expected_revision >= 0
        and isinstance(next_run_at, datetime)
        and timezone.is_aware(next_run_at),
        'invalid_automation',
        'Informe horizonte/lote limitados, frequência positiva, revisão e instante com fuso.',
    )
    require(
        not enabled or ResponsePolicy.objects.filter(route_group=group).exists(),
        'policy_missing',
        'Configure a política de respostas antes de habilitar a geração.',
    )
    values = dict(
        zip(CONFIGURATION_FIELDS, (enabled, horizon_days, batch_size, interval_seconds, next_run_at), strict=True)
    )
    schedule = AutomationSchedule.objects.select_for_update().filter(route_group=group).first()
    require(
        expected_revision == (schedule.revision if schedule else 0),
        'stale_revision',
        'A agenda automática foi alterada.',
    )
    if schedule and all(getattr(schedule, name) == value for name, value in values.items()):
        return schedule
    if schedule is None:
        schedule = AutomationSchedule(route_group=group)
    else:
        schedule.revision += 1
    for name, value in values.items():
        setattr(schedule, name, value)
    schedule.cursor_date = schedule.cycle_end_date = None
    schedule.last_error_code = ''
    schedule.configured_by_id, schedule.configured_at = actor_id, timezone.now()
    schedule.full_clean()
    schedule.save()
    return schedule


@transaction.atomic
def _advance(*, actor_id, company_id, schedule_id):
    company_actor(lock_company(company_id), actor_id)
    schedule = get(
        AutomationSchedule.objects.select_for_update().filter(route_group__company_id=company_id), pk=schedule_id
    )
    now = timezone.now()
    if not schedule.enabled or schedule.next_run_at > now:
        return None
    today = timezone.localdate(now)
    cursor = max(schedule.cursor_date or today, today)
    end = schedule.cycle_end_date or today + timedelta(days=schedule.horizon_days - 1)
    schedule.last_attempted_at = now
    processed = 0
    try:
        # Se o lote falhar/interromper, nem as datas desse lote nem seu checkpoint avançam.
        with transaction.atomic():
            while cursor <= end and processed < schedule.batch_size:
                generate_day(actor_id=actor_id, group_id=schedule.route_group_id, date=cursor)
                cursor += timedelta(days=1)
                processed += 1
    except ValidationError:
        schedule.last_error_code = 'generation_blocked'
        schedule.next_run_at = now + timedelta(seconds=schedule.interval_seconds)
        schedule.save(update_fields=['last_attempted_at', 'last_error_code', 'next_run_at'])
        return {'status': 'blocked', 'processed': 0}
    schedule.last_error_code = ''
    if cursor > end:
        schedule.cursor_date = schedule.cycle_end_date = None
        schedule.last_completed_at = now
        schedule.next_run_at = now + timedelta(seconds=schedule.interval_seconds)
        status = 'completed'
    else:
        schedule.cursor_date, schedule.cycle_end_date = cursor, end
        # Volta para o fim da fila vencida, em vez de monopolizar outros grupos.
        schedule.next_run_at = now
        status = 'partial'
    schedule.save(
        update_fields=[
            'cursor_date',
            'cycle_end_date',
            'last_attempted_at',
            'last_completed_at',
            'last_error_code',
            'next_run_at',
        ]
    )
    return {'status': status, 'processed': processed}


def process_schedules(*, actor_id, company_id, batch_size):
    require(type(batch_size) is int and 1 <= batch_size <= 1000, 'invalid_batch', 'Informe lote entre 1 e 1000.')
    # A seleção é limitada; cada agenda é revalidada sob o mutex empresarial.
    ids = list(
        AutomationSchedule.objects
        .filter(route_group__company_id=company_id, enabled=True, next_run_at__lte=timezone.now())
        .order_by('next_run_at', F('last_attempted_at').asc(nulls_first=True), 'pk')
        .values_list('pk', flat=True)[:batch_size]
    )
    return [result for pk in ids if (result := _advance(actor_id=actor_id, company_id=company_id, schedule_id=pk))]
