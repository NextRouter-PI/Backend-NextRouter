"""Geração, regeneração e revisão transacional de dias de atendimento."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from modules.transport.models import ResponsePolicy, ServiceDay
from modules.transport.services.locking import group_access
from shared.exceptions import get, require

from .eligibility_sync import sync_day_eligibilities
from .snapshot_builder import active_services_for_date, build_day_configuration
from .travel_sync import sync_day_travels


def _generate(group, date, *, explicit: bool = False) -> ServiceDay:
    now = timezone.now()
    require(date >= timezone.localdate(now), 'past_date', 'Não gere atendimentos passados.')
    existing = ServiceDay.objects.filter(route_group=group, date=date).first()
    if existing and (
        existing.canceled_at
        or (not explicit and (date <= timezone.localdate(now) or existing.has_published_travels()))
        or existing.has_started_execution()
    ):
        return existing

    policy = get(ResponsePolicy.objects.all(), route_group=group) if existing is None else None
    if existing is not None and explicit:
        policy = ResponsePolicy.objects.filter(route_group=group).first()

    services = active_services_for_date(group, date)
    configuration = build_day_configuration(group, services, existing=existing)

    if existing is None:
        opens_at, normal_deadline, extension_deadline = policy.window_for(date)
        day = ServiceDay(
            route_group=group,
            date=date,
            opens_at=opens_at,
            normal_deadline=normal_deadline,
            extension_deadline=extension_deadline,
        )
        day.full_clean()
        day.save()
    else:
        day = existing

    sync_day_eligibilities(day, group, services, configuration)
    sync_day_travels(
        day,
        group,
        date,
        configuration,
        previous_snapshot=existing.configuration_snapshot if existing is not None else None,
    )

    old_snapshot = day.configuration_snapshot
    deadlines_changed = False
    if existing and explicit and policy is not None:
        new_opens, new_normal, new_extension = policy.window_for(date)
        if day.opens_at != new_opens or day.normal_deadline != new_normal or day.extension_deadline != new_extension:
            day.opens_at = new_opens
            day.normal_deadline = new_normal
            day.extension_deadline = new_extension
            day.full_clean()
            deadlines_changed = True

    if existing and (old_snapshot != configuration or deadlines_changed):
        day.revision += 1
    day.configuration_snapshot = configuration
    update_fields = ['configuration_snapshot', 'revision']
    if deadlines_changed:
        update_fields.extend(['opens_at', 'normal_deadline', 'extension_deadline'])
    day.save(update_fields=update_fields)

    if configuration['issues']:
        day.travels.filter(status='scheduled').update(planning_status='blocked')
    return day


@transaction.atomic
def generate_day(*, actor_id, group_id, date):
    return _generate(group_access(group_id, actor_id), date)


def regenerate_future_days(group):
    # Chamador já mantém o mutex empresarial. Não reabre datas nem muda prazos efetivos.
    for date in group.days.future().order_by('date').values_list('date', flat=True):
        _generate(group, date)


@transaction.atomic
def revise_day(*, actor_id, day_id, expected_revision):
    initial = get(ServiceDay.objects.all(), pk=day_id)
    group = group_access(initial.route_group_id, actor_id)
    day = get(ServiceDay.objects.filter(route_group=group), pk=day_id)
    require(day.revision == expected_revision, 'stale_revision', 'O atendimento foi alterado.')
    require(
        not day.canceled_at and not day.has_started_execution(),
        'execution_started',
        'A revisão do atendimento exige viagens ainda não iniciadas.',
    )
    return _generate(group, day.date, explicit=True)


@transaction.atomic
def generate_horizon(*, actor_id, group_id, start_date, horizon_days, batch_size, excluded_dates=None):
    require(
        type(horizon_days) is int and horizon_days > 0 and type(batch_size) is int and batch_size > 0,
        'invalid_horizon',
        'Informe horizonte e lote positivos.',
    )
    require(
        start_date > timezone.localdate(),
        'past_or_today_date',
        'Não é permitido aplicar atendimentos no dia atual nem em datas passadas. Escolha a partir de amanhã.',
    )
    excluded = set(excluded_dates or [])
    group = group_access(group_id, actor_id)
    days = []
    for offset in range(min(horizon_days, batch_size)):
        target_date = start_date + timedelta(days=offset)
        if target_date in excluded:
            continue
        days.append(_generate(group, target_date))
    return days
