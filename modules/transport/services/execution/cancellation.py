"""Cancelamento de viagem, dia de atendimento e data futura (tombstone)."""

from django.db import transaction
from django.utils import timezone

from modules.transport.models import (
    DailyChangeRequest,
    ResponsePolicy,
    RouteOptimizationJob,
    ServiceDay,
    Travel,
)
from modules.transport.services.actors import company_actor
from modules.transport.services.locking import group_access, lock_for_company, lock_travel
from modules.transport.services.notifications import notify, travel_recipients
from shared.exceptions import get, require


def cancel_travel_locked(travel: Travel) -> Travel:
    if travel.status == Travel.Status.CANCELED:
        return travel
    require(travel.status == Travel.Status.SCHEDULED, 'execution_started', 'Não cancele viagem já iniciada.')
    now = timezone.now()
    for request in DailyChangeRequest.objects.filter(
        response__eligibility__day_id=travel.service_day_id,
        proposed_service_id=travel.service_id,
        status=DailyChangeRequest.Status.PENDING,
    ).order_by('pk'):
        request.supersede(now=now)
    for snapshot in (
        travel.route_snapshots
        .filter(change_request__application='preparing')
        .select_related('change_request')
        .order_by('pk')
    ):
        if snapshot.change_request.status == DailyChangeRequest.Status.APPROVED:
            snapshot.change_request.supersede(now=now)
    travel.route_snapshots.filter(state='pending').update(state='superseded')
    # Cancela em 1 único UPDATE todos os jobs pendentes/ativos dos snapshots desta viagem.
    RouteOptimizationJob.objects.filter(
        snapshot__travel=travel,
        status__in=[RouteOptimizationJob.Status.PENDING, RouteOptimizationJob.Status.RUNNING],
    ).update(
        status=RouteOptimizationJob.Status.FAILED,
        error='travel_canceled',
        claim_token=None,
        claim_expires_at=None,
    )
    travel.driver_invitations.filter(status='pending').update(status='revoked', closed_at=now, is_current=False)
    travel.mark_canceled()
    notify(
        recipients=travel_recipients(travel),
        kind='cancellation',
        resource_type='travel',
        resource_id=travel.pk,
        key=f'travel:{travel.pk}:cancel',
        status='canceled',
    )
    return travel


@transaction.atomic
def cancel_travel(*, actor_id, travel_id):
    company, travel = lock_travel(travel_id)
    company_actor(company, actor_id)
    return cancel_travel_locked(travel)


@transaction.atomic
def cancel_day(*, actor_id, day_id, reason):
    company, day = lock_for_company(
        ServiceDay.objects.all(),
        day_id,
        company_getter=lambda item: item.route_group.company_id,
        company_filter='route_group__company',
    )
    company_actor(company, actor_id)
    require(
        isinstance(reason, str) and 0 < len(reason.strip()) <= 500,
        'reason_required',
        'Informe o motivo do cancelamento.',
    )
    now = timezone.now()
    if not day.canceled_at:
        day.canceled_at = now
        day.canceled_by_id = actor_id
        day.cancellation_reason = reason.strip()
        day.save(update_fields=['canceled_at', 'canceled_by', 'cancellation_reason'])

    for request in DailyChangeRequest.objects.open_requests().filter(response__eligibility__day=day).order_by('pk'):
        request.supersede(now=now)

    preserved = []
    for travel in day.travels.order_by('pk'):
        if travel.status in (Travel.Status.IN_PROGRESS, Travel.Status.FINISHED):
            preserved.append(travel.pk)
        else:
            cancel_travel_locked(travel)
    notify(
        recipients=[company.user_id, *day.eligibilities.values_list('passenger__user_id', flat=True)],
        kind='cancellation',
        resource_type='service_day',
        resource_id=day.pk,
        key=f'day:{day.pk}:cancel',
        status='canceled',
    )
    return {'day': day, 'preserved_travel_ids': preserved, 'partial': bool(preserved)}


@transaction.atomic
def cancel_date(*, actor_id, group_id, date, reason):
    """Tombstone mesmo antes de gerar viagens ou elegibilidades daquela data."""
    group = group_access(group_id, actor_id)
    require(date >= timezone.localdate(), 'past_date', 'Não cancele retroativamente uma data não gerada.')
    day = ServiceDay.objects.filter(route_group=group, date=date).first()
    if day is None:
        policy = get(ResponsePolicy.objects.all(), route_group=group)
        opens_at, normal_deadline, extension_deadline = policy.window_for(date)
        day = ServiceDay.objects.create(
            route_group=group,
            date=date,
            opens_at=opens_at,
            normal_deadline=normal_deadline,
            extension_deadline=extension_deadline,
        )
    result = cancel_day(actor_id=actor_id, day_id=day.pk, reason=reason)
    recipients = group.passenger_memberships.filter(ended_at=None, membership__status='active').values_list(
        'membership__passenger__user_id',
        flat=True,
    )
    notify(
        recipients=recipients,
        kind='cancellation',
        resource_type='service_day',
        resource_id=day.pk,
        key=f'day:{day.pk}:cancel',
        status='canceled',
    )
    return result
