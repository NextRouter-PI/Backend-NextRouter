"""Aplicação atômica em duas fases de pedidos de alteração diária aprovados."""

from uuid import NAMESPACE_URL, uuid5

from django.db import transaction
from django.utils import timezone

from modules.transport.models import (
    DailyChangeRequest,
    ParticipationEvent,
    RouteSnapshot,
    SeatReservation,
    Travel,
    TravelParticipation,
)
from modules.transport.services.actors import company_actor
from modules.transport.services.demand import selected_service
from modules.transport.services.notifications import notify
from modules.transport.services.planning import capacity, validate_agenda, validate_designations, validate_roster
from modules.transport.services.routing import materialize_stops
from shared.exceptions import get, require

from .lifecycle import request_access


def _validate_application(request: DailyChangeRequest) -> tuple[Travel, list[RouteSnapshot]]:
    require(
        request.status == DailyChangeRequest.Status.APPROVED
        and request.application == DailyChangeRequest.Application.PREPARING,
        'request_not_preparing',
        'Não há proposta em preparação.',
    )
    require(request.is_leg_unchanged(), 'stale_revision', 'A escolha anterior foi alterada.')
    snapshots = list(request.route_snapshots.select_related('travel').order_by('travel_id'))
    require(
        snapshots and all(snapshot.state == RouteSnapshot.State.READY for snapshot in snapshots),
        'route_not_ready',
        'O cálculo da proposta não está pronto.',
    )
    eligibility = request.response.eligibility
    target = get(Travel.objects.filter(service_day=eligibility.day, service_id=request.proposed_service_id))
    source_ids = set(
        eligibility.participations
        .active_occupancy()
        .filter(leg=request.leg)
        .exclude(travel__status='canceled')
        .values_list('travel_id', flat=True)
    )
    require(
        {target.pk, *source_ids} == {snapshot.travel_id for snapshot in snapshots},
        'stale_revision',
        'As viagens envolvidas mudaram depois da aprovação.',
    )
    periods = {snapshot.travel_id: (snapshot.planned_start, snapshot.planned_end) for snapshot in snapshots}
    for snapshot in snapshots:
        snapshot.full_clean()
        require(
            snapshot.optimization_jobs.filter(
                status='done', frozen_input=snapshot.input_data, input_revision=snapshot.base_revision
            ).exists(),
            'route_not_ready',
            'A revisão não possui cálculo concluído correspondente.',
        )
        travel = snapshot.travel
        travel.ensure_editable()
        validate_designations(travel)
        validate_roster(travel)
        capacity(travel)
        expected_ids = set(travel.participations.filter(status='allocated').values_list('eligibility_id', flat=True))
        expected_ids.discard(request.response.eligibility_id)
        if travel.service_id == request.proposed_service_id:
            expected_ids.add(request.response.eligibility_id)
        require(
            expected_ids == {p['eligibility_id'] for p in snapshot.input_data['participants']}
            and snapshot.input_data.get('driver_id') == travel.driver_id
            and snapshot.input_data.get('vehicle_id') == travel.vehicle_id,
            'stale_revision',
            'As entradas da proposta não correspondem à operação atual.',
        )
        require(
            snapshot.planned_start is not None
            and snapshot.planned_end is not None
            and travel.revision == snapshot.base_revision,
            'stale_revision',
            'A viagem foi alterada depois da preparação.',
        )
        travel.planned_start, travel.planned_end = snapshot.planned_start, snapshot.planned_end
        validate_agenda(travel, overrides=periods)
    return target, snapshots


def _transfer_seat(request: DailyChangeRequest, *, target: Travel, actor_id, now) -> None:
    held = get(SeatReservation.objects.filter(request=request, travel=target, status='held'))
    capacity(target, additional=1, exclude_request_id=request.pk)
    eligibility = request.response.eligibility
    selected_service(eligibility, request.proposed_service_id, request.leg)

    for participant in eligibility.participations.active_occupancy().filter(leg=request.leg):
        require(
            participant.status == TravelParticipation.Status.ALLOCATED, 'already_boarded', 'O passageiro já embarcou.'
        )
        participant.status = TravelParticipation.Status.WITHDRAWN
        participant.withdrawn_at = now
        participant.save(update_fields=['status', 'withdrawn_at'])
        ParticipationEvent.objects.create(
            participation=participant,
            kind=ParticipationEvent.Kind.WITHDRAWN,
            actor_id=actor_id,
            occurred_at=now,
            operation_id=uuid5(NAMESPACE_URL, f'request:{request.pk}:transfer'),
        )

    participant = TravelParticipation.objects.filter(travel=target, eligibility=eligibility).first()
    if participant is None:
        participant = TravelParticipation(travel=target, eligibility=eligibility, leg=request.leg, allocated_at=now)
    else:
        participant.status = TravelParticipation.Status.ALLOCATED
        participant.allocated_at = now
        participant.withdrawn_at = participant.no_show_at = participant.boarded_at = participant.dropped_off_at = None
    participant.full_clean()
    participant.save()
    ParticipationEvent.objects.create(
        participation=participant,
        kind=ParticipationEvent.Kind.ALLOCATED,
        actor_id=actor_id,
        occurred_at=now,
        operation_id=uuid5(NAMESPACE_URL, f'request:{request.pk}:allocation'),
    )

    response = request.response
    response.apply_leg_choice(request.leg, request.proposed_service_id, now=now)
    response.save(update_fields=[f'{request.leg}_service', f'{request.leg}_withdrawn_at', 'revision', 'answered_at'])

    held.status = SeatReservation.Status.CONSUMED
    held.closed_at = now
    held.save(update_fields=['status', 'closed_at'])
    request.mark_applied(now=now)


def _promote_snapshots(snapshots: list[RouteSnapshot]) -> None:
    for snapshot in snapshots:
        travel = snapshot.travel
        travel.revision = snapshot.revision
        travel.current_snapshot = snapshot
        travel.planning_status = Travel.PlanningStatus.READY
        travel.planned_start = snapshot.planned_start
        travel.planned_end = snapshot.planned_end
        travel.save(update_fields=['revision', 'current_snapshot', 'planning_status', 'planned_start', 'planned_end'])
        materialize_stops(snapshot)


@transaction.atomic
def apply_request(*, actor_id, request_id):
    company, request = request_access(request_id, actor_id, company_only=True)
    company_actor(company, actor_id)
    if request.application == DailyChangeRequest.Application.APPLIED:
        return request
    target, snapshots = _validate_application(request)
    now = timezone.now()
    _transfer_seat(request, target=target, actor_id=actor_id, now=now)
    _promote_snapshots(snapshots)
    notify(
        recipients=[request.requested_by_id, company.user_id],
        kind='request',
        resource_type='request',
        resource_id=request.pk,
        key=f'request:{request.pk}:applied',
        status='applied',
    )
    return request
