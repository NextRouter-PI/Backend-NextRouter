"""Ciclo de vida de execução da viagem: início e finalização pelo motorista."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from modules.transport.broadcast import close_travel_after_commit
from modules.transport.models import Travel
from modules.transport.services.actors import driver_actor
from modules.transport.services.locking import lock_travel
from modules.transport.services.notifications import notify, travel_recipients
from modules.transport.services.planning import publish_travel, ready_requirements
from modules.transport.services.tracking import location_cache_key
from shared.exceptions import require

logger = logging.getLogger(__name__)


@transaction.atomic
def start_travel(*, actor_id, travel_id, expected_revision):
    _, travel = lock_travel(travel_id)
    driver_actor(travel, actor_id)
    require(travel.revision == expected_revision, 'stale_revision', 'A viagem foi alterada.')
    if travel.status == Travel.Status.IN_PROGRESS:
        return travel
    require(
        travel.planning_status == Travel.PlanningStatus.READY,
        'planning_not_ready',
        'O planejamento não está pronto.',
    )
    ready_requirements(travel)
    now = timezone.now()
    early = timedelta(minutes=settings.TRAVEL_START_EARLY_MINUTES)
    require(
        travel.planned_start is None or now >= travel.planned_start - early,
        'too_early_to_start',
        f'A viagem só pode ser iniciada a partir de {settings.TRAVEL_START_EARLY_MINUTES} min antes da saída.',
    )
    if not travel.is_published_current:
        # Rota pronta e no horário: o início publica a revisão atual; a empresa não precisa validar antes.
        publish_travel(actor_id=travel.company.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        travel.refresh_from_db()
    require(
        not Travel.objects
        .active()
        .conflicting_resources(driver_id=travel.driver_id, vehicle_id=travel.vehicle_id, exclude_pk=travel.pk)
        .exists(),
        'active_resource',
        'Motorista/veículo já está em viagem.',
    )
    travel.mark_started(now=now)
    notify(
        recipients=travel_recipients(travel),
        kind='operation',
        resource_type='travel',
        resource_id=travel.pk,
        key=f'travel:{travel.pk}:start',
        status='in_progress',
    )
    return travel


@transaction.atomic
def finish_travel(*, actor_id, travel_id):
    _, travel = lock_travel(travel_id)
    driver_actor(travel, actor_id)
    if travel.status == Travel.Status.FINISHED:
        return travel
    require(travel.status == Travel.Status.IN_PROGRESS, 'travel_not_active', 'A viagem não está em andamento.')
    require(
        not travel.participations.filter(status='on_board').exists(),
        'passengers_on_board',
        'Registre os desembarques antes de finalizar.',
    )
    require(
        not travel.participations.filter(status='allocated').exists(),
        'pending_participants',
        'Registre a presença/ausência dos participantes antes de finalizar.',
    )
    travel.mark_finished(now=timezone.now())

    def clear_location_cache():
        try:
            cache.delete(location_cache_key(travel.pk))
        except Exception:
            logger.warning('location_cache_clear_failed travel_id=%s', travel.pk)

    transaction.on_commit(clear_location_cache)
    close_travel_after_commit(travel.pk)
    notify(
        recipients=travel_recipients(travel),
        kind='operation',
        resource_type='travel',
        resource_id=travel.pk,
        key=f'travel:{travel.pk}:finish',
        status='finished',
    )
    return travel
