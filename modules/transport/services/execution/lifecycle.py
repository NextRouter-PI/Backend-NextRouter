"""Ciclo de vida de execução da viagem: início e finalização pelo motorista."""

from django.db import transaction
from django.utils import timezone

from modules.transport.broadcast import close_travel_after_commit
from modules.transport.models import Travel
from modules.transport.services.actors import driver_actor
from modules.transport.services.locking import lock_travel
from modules.transport.services.notifications import notify, travel_recipients
from modules.transport.services.planning import ready_requirements
from shared.exceptions import require


@transaction.atomic
def start_travel(*, actor_id, travel_id, expected_revision):
    _, travel = lock_travel(travel_id)
    driver_actor(travel, actor_id)
    require(travel.revision == expected_revision, 'stale_revision', 'A viagem foi alterada.')
    if travel.status == Travel.Status.IN_PROGRESS:
        return travel
    require(
        travel.is_published_current,
        'publication_outdated',
        'A revisão atual precisa estar publicada.',
    )
    require(
        travel.planning_status == Travel.PlanningStatus.READY,
        'planning_not_ready',
        'O planejamento não está pronto.',
    )
    ready_requirements(travel)
    require(
        not Travel.objects
        .active()
        .conflicting_resources(driver_id=travel.driver_id, vehicle_id=travel.vehicle_id, exclude_pk=travel.pk)
        .exists(),
        'active_resource',
        'Motorista/veículo já está em viagem.',
    )
    travel.mark_started(now=timezone.now())
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
