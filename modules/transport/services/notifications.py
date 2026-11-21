"""Emissão em lote e leitura de notificações operacionais."""

from django.db import transaction
from django.utils import timezone

from modules.transport.models import Notification
from shared.exceptions import get

from .actors import active_actor


def notify(*, recipients, kind, resource_type, resource_id, key, status, revision=None):
    return Notification.objects.emit_bulk(
        recipients=recipients,
        kind=kind,
        resource_type=resource_type,
        resource_id=resource_id,
        key=key,
        status=status,
        revision=revision,
    )


def travel_recipients(travel):
    return travel.recipient_user_ids()


@transaction.atomic
def read_notification(*, actor_id, notification_id):
    active_actor(actor_id)
    notification = get(Notification.objects.select_for_update().filter(recipient_id=actor_id), pk=notification_id)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at'])
    return notification


def emit_membership_notification_in_transport(
    *, recipient_id, membership_id, deduplication_key: str, status: str, occurred_at
) -> None:
    Notification.objects.create(
        recipient_id=recipient_id,
        kind=Notification.Kind.MEMBERSHIP,
        resource_type=Notification.ResourceType.MEMBERSHIP,
        resource_id=str(membership_id),
        deduplication_key=deduplication_key,
        payload={'status': status},
        created_at=occurred_at,
    )
