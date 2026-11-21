"""Cálculo explícito, publicação de revisão e designação de veículo da viagem."""

from django.db import transaction

from modules.transport.models import Travel, TravelPublication, Vehicle
from modules.transport.services.actors import company_actor
from modules.transport.services.calendar import point_data
from modules.transport.services.locking import lock_travel
from modules.transport.services.notifications import notify, travel_recipients
from shared.exceptions import get, require

from .closing import prepare_route
from .validators import capacity, frozen_service, ready_requirements


@transaction.atomic
def calculate_travel(*, actor_id, travel_id, expected_revision):
    company, travel = lock_travel(travel_id)
    company_actor(company, actor_id)
    require(travel.revision == expected_revision, 'stale_revision', 'A viagem foi alterada.')
    require(
        not travel.route_snapshots.filter(change_request__application='preparing').exists(),
        'proposal_pending',
        'Há alteração aprovada em preparação.',
    )
    return prepare_route(travel)


@transaction.atomic
def publish_travel(*, actor_id, travel_id, expected_revision):
    company, travel = lock_travel(travel_id)
    company_actor(company, actor_id)
    require(travel.revision == expected_revision, 'stale_revision', 'A viagem foi alterada.')
    require(
        travel.planning_status == Travel.PlanningStatus.READY,
        'planning_not_ready',
        'O planejamento não está pronto.',
    )
    ready_requirements(travel)
    publication, created = TravelPublication.objects.get_or_create(
        travel=travel,
        revision=travel.revision,
        defaults={'snapshot': travel.current_snapshot, 'published_by_id': actor_id},
    )
    travel.published_revision = travel.revision
    travel.published_snapshot = travel.current_snapshot
    travel.save(update_fields=['published_revision', 'published_snapshot'])
    if created:
        notify(
            recipients=travel_recipients(travel),
            kind='publication',
            resource_type='travel',
            resource_id=travel.pk,
            key=f'publication:{travel.pk}:{travel.revision}',
            status='published',
            revision=travel.revision,
        )
    return publication


@transaction.atomic
def assign_vehicle(*, actor_id, travel_id, vehicle_id):
    company, travel = lock_travel(travel_id)
    company_actor(company, actor_id)
    travel.ensure_editable()
    vehicle = get(Vehicle.objects.filter(company=company, status='active'), pk=vehicle_id)
    if travel.vehicle_id == vehicle.pk:
        return travel
    travel.vehicle = vehicle
    capacity(travel)
    data = frozen_service(travel)
    data['vehicle_id'] = vehicle.pk
    if travel.service.origin_id is None:
        data['origin'] = point_data(vehicle.garage_point)
    day = travel.service_day
    day.save(update_fields=['configuration_snapshot'])
    travel.save(update_fields=['vehicle'])
    travel.invalidate()
    return travel
