"""Passo reentrante para futuro worker; limites são argumentos, não políticas globais."""

from django.db import transaction
from django.utils import timezone

from modules.transport.models import DailyChangeRequest, DriverInvitation, Notification, ServiceDay

from .common import active_actor, company_actor, get, lock_company, notify
from .planning import close_day
from .requests import supersede_request


@transaction.atomic
def process_due(*, actor_id, company_id):
    company = lock_company(company_id)
    company_actor(company, actor_id)
    now = timezone.now()
    for request in DailyChangeRequest.objects.filter(
        response__eligibility__day__route_group__company=company, status='pending', expires_at__lte=now
    ).order_by('pk'):
        supersede_request(request, now=now, status='expired')
        notify(
            recipients=[request.requested_by_id],
            kind='request',
            resource_type='request',
            resource_id=request.pk,
            key=f'request:{request.pk}:expired',
            status='expired',
        )
    for invitation in DriverInvitation.objects.filter(travel__company=company, status='pending', expires_at__lte=now):
        invitation.status, invitation.closed_at = 'expired', now
        invitation.save(update_fields=['status', 'closed_at'])
        notify(
            recipients=[company.user_id, invitation.driver_membership.driver.user_id],
            kind='invitation',
            resource_type='invitation',
            resource_id=invitation.pk,
            key=f'invitation:{invitation.pk}:expired',
            status='expired',
        )
    outcomes = {}
    from .common import DomainError

    for day in ServiceDay.objects.filter(route_group__company=company, canceled_at=None, normal_deadline__lte=now):
        if day.configuration_snapshot.get('closed_revision') == day.revision:
            continue
        try:
            with transaction.atomic():
                close_day(actor_id=actor_id, day_id=day.pk)
            outcomes[day.pk] = 'closed'
        except DomainError as exc:
            outcomes[day.pk] = exc.code
            day.refresh_from_db()
            day.configuration_snapshot = {**day.configuration_snapshot, 'operational_issue': exc.code}
            day.save(update_fields=['configuration_snapshot'])
            day.travels.filter(status='scheduled').update(planning_status='blocked')
    return outcomes


@transaction.atomic
def read_notification(*, actor_id, notification_id):
    active_actor(actor_id)
    notification = get(Notification.objects.select_for_update().filter(recipient_id=actor_id), pk=notification_id)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
    return notification
