"""Registro e custódia auditada de objetos perdidos."""

from django.db import transaction
from django.utils import timezone

from modules.transport.models import LostItem, LostItemEvent
from shared.exceptions import get, require

from .actors import company_actor
from .idempotency import check_idempotent_operation
from .locking import lock_travel
from .ratings import history_actor


@transaction.atomic
def report_lost_item(*, actor_id, travel_id, item_description, operation_id):
    _, travel = lock_travel(travel_id)
    history_actor(travel, actor_id)
    require(
        isinstance(item_description, str) and 0 < len(item_description.strip()) <= 255,
        'invalid_description',
        'Informe uma descrição de até 255 caracteres.',
    )
    clean_description = item_description.strip()
    old = check_idempotent_operation(
        LostItemEvent.objects.select_related('item'),
        operation_id=operation_id,
        matches=lambda event: (
            event.actor_id == actor_id
            and event.item.travel_id == travel.pk
            and event.status == LostItem.Status.REPORTED
            and event.item.item_description == clean_description
        ),
        conflict_message='O identificador já foi utilizado.',
    )
    if old:
        return old.item
    item = LostItem.objects.create(travel=travel, user_id=actor_id, item_description=clean_description)
    LostItemEvent.objects.create(
        item=item,
        status=LostItem.Status.REPORTED,
        actor_id=actor_id,
        operation_id=operation_id,
        occurred_at=timezone.now(),
    )
    return item


@transaction.atomic
def transition_lost_item(*, actor_id, item_id, target_status, operation_id):
    initial = get(LostItem.objects.all(), pk=item_id)
    company, travel = lock_travel(initial.travel_id)
    company_actor(company, actor_id)
    item = get(LostItem.objects.select_for_update().filter(travel=travel), pk=item_id)
    old = check_idempotent_operation(
        LostItemEvent.objects,
        operation_id=operation_id,
        matches=lambda event: event.item_id == item.pk and event.actor_id == actor_id and event.status == target_status,
        conflict_message='O identificador já foi utilizado.',
    )
    if old:
        return item
    item.transition_to(target_status)
    LostItemEvent.objects.create(
        item=item,
        status=target_status,
        actor_id=actor_id,
        operation_id=operation_id,
        occurred_at=timezone.now(),
    )
    return item
