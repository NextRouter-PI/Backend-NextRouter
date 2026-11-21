"""Avanço operacional de paradas no percurso em execução."""

from django.db import transaction
from django.utils import timezone

from modules.transport.models import RouteStop, Travel
from modules.transport.services.actors import driver_actor
from modules.transport.services.locking import lock_travel
from shared.exceptions import get, require


@transaction.atomic
def handle_stop(*, actor_id, stop_id, skipped=False):
    initial = get(RouteStop.objects.all(), pk=stop_id)
    _, travel = lock_travel(initial.snapshot.travel_id)
    driver_actor(travel, actor_id)
    require(
        travel.status == Travel.Status.IN_PROGRESS and travel.current_snapshot_id == initial.snapshot_id,
        'route_not_current',
        'A parada não pertence ao percurso em execução.',
    )
    stop = get(RouteStop.objects.select_for_update(), pk=stop_id)
    if stop.ensure_can_handle(skipped=skipped):
        stop.mark_handled(actor_id=actor_id, now=timezone.now(), skipped=skipped)
    return stop
