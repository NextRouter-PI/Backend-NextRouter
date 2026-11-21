"""Manutenção reentrante, limitada por tipo, com transações isoladas por item e rotação de bloqueios."""

from django.db import transaction
from django.utils import timezone

from modules.transport.models import DailyChangeRequest, DriverInvitation, ServiceDay
from shared.exceptions import DomainError, require

from .actors import company_actor
from .locking import lock_company
from .notifications import notify, read_notification
from .planning import close_day

__all__ = ['process_due', 'read_notification']


@transaction.atomic
def _expire_request(*, actor_id, company_id, request_id, now) -> None:
    company = lock_company(company_id)
    company_actor(company, actor_id)
    request = (
        DailyChangeRequest.objects
        .select_for_update(of=('self',))
        .expired_pending(now=now)
        .filter(pk=request_id, response__eligibility__day__route_group__company=company)
        .first()
    )
    if request is None:
        return
    request.supersede(now=now, status=DailyChangeRequest.Status.EXPIRED)
    notify(
        recipients=[request.requested_by_id],
        kind='request',
        resource_type='request',
        resource_id=request.pk,
        key=f'request:{request.pk}:expired',
        status='expired',
    )


@transaction.atomic
def _expire_invitation(*, actor_id, company_id, invitation_id, now) -> None:
    company = lock_company(company_id)
    company_actor(company, actor_id)
    invitation = (
        DriverInvitation.objects
        .select_for_update(of=('self',))
        .select_related('driver_membership__driver')
        .expired_pending(now=now)
        .filter(pk=invitation_id, travel__company=company)
        .first()
    )
    if invitation is None:
        return
    invitation.status = DriverInvitation.Status.EXPIRED
    invitation.closed_at = now
    invitation.save(update_fields=['status', 'closed_at'])
    notify(
        recipients=[company.user_id, invitation.driver_membership.driver.user_id],
        kind='invitation',
        resource_type='invitation',
        resource_id=invitation.pk,
        key=f'invitation:{invitation.pk}:expired',
        status='expired',
    )


@transaction.atomic
def _close_due_day(*, actor_id, company_id, day_id, now) -> str | None:
    company = lock_company(company_id)
    company_actor(company, actor_id)
    day = (
        ServiceDay.objects
        .select_for_update(of=('self',))
        .filter(pk=day_id, route_group__company=company, canceled_at=None, normal_deadline__lte=now)
        .first()
    )
    if day is None or day.configuration_snapshot.get('closed_revision') == day.revision:
        return None
    try:
        with transaction.atomic():
            close_day(actor_id=actor_id, day_id=day.pk)
        outcome = 'closed'
    except DomainError as exc:
        outcome = exc.code
        day.refresh_from_db()
        day.configuration_snapshot = {**day.configuration_snapshot, 'operational_issue': exc.code}
        day.save(update_fields=['configuration_snapshot'])
        day.travels.filter(status='scheduled').update(planning_status='blocked')
    day.refresh_from_db()
    day.configuration_snapshot = {**day.configuration_snapshot, 'maintenance_attempted_at': now.isoformat()}
    day.save(update_fields=['configuration_snapshot'])
    return outcome


def process_due(*, actor_id, company_id, batch_size):
    require(type(batch_size) is int and 1 <= batch_size <= 1000, 'invalid_batch', 'Informe lote entre 1 e 1000.')
    with transaction.atomic():
        company = lock_company(company_id)
        company_actor(company, actor_id)
        now = timezone.now()
        expired_request_ids = list(
            DailyChangeRequest.objects
            .expired_pending(now=now)
            .filter(response__eligibility__day__route_group__company=company)
            .order_by('expires_at', 'pk')
            .values_list('pk', flat=True)[:batch_size]
        )
        expired_invitation_ids = list(
            DriverInvitation.objects
            .expired_pending(now=now)
            .filter(travel__company=company)
            .order_by('expires_at', 'pk')
            .values_list('pk', flat=True)[:batch_size]
        )
        due_day_ids = list(
            ServiceDay.objects.due_for_closing(company=company, now=now).values_list('pk', flat=True)[:batch_size]
        )

    for request_id in expired_request_ids:
        _expire_request(actor_id=actor_id, company_id=company_id, request_id=request_id, now=now)
    for invitation_id in expired_invitation_ids:
        _expire_invitation(actor_id=actor_id, company_id=company_id, invitation_id=invitation_id, now=now)

    outcomes = {}
    for day_id in due_day_ids:
        outcome = _close_due_day(actor_id=actor_id, company_id=company_id, day_id=day_id, now=now)
        if outcome is not None:
            outcomes[day_id] = outcome
    return outcomes
