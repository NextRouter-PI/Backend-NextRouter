from uuid import NAMESPACE_URL, uuid5

from django.db import transaction
from django.utils import timezone

from modules.transport.models import (
    DailyChangeRequest,
    DailyResponse,
    ParticipationEvent,
    SeatReservation,
    Travel,
    TravelParticipation,
)

from .common import company_actor, editable, get, notify, require
from .demand import eligibility_access, selected_service
from .planning import capacity, prepare_route, validate_agenda, validate_designations, validate_roster


def unchanged_leg(request):
    response = request.response
    withdrawn = getattr(response, f'{request.leg}_withdrawn_at')
    return getattr(response, f'{request.leg}_service_id') == request.previous_choice_snapshot['service_id'] and (
        withdrawn.isoformat() if withdrawn else None
    ) == request.previous_choice_snapshot.get('withdrawn_at')


def supersede_request(request, *, now, status='superseded'):
    require(request.application != 'applied', 'request_applied', 'A alteração já foi aplicada.')
    request.status, request.closed_at = status, now
    if request.application == 'preparing':
        request.application = 'failed'
    request.save(update_fields=['status', 'closed_at', 'application'])
    request.seat_reservations.filter(status='held').update(status='released', closed_at=now)
    for snapshot in request.route_snapshots.select_related('travel').order_by('travel_id'):
        snapshot.state = 'superseded'
        snapshot.save(update_fields=['state'])
        snapshot.optimization_jobs.exclude(status='done').update(
            status='failed',
            error='proposal_closed',
            claim_token=None,
            claim_expires_at=None,
        )
        restore_previous(snapshot.travel)


def restore_previous(travel):
    if travel.status == 'scheduled':
        snapshot = travel.current_snapshot
        pending = travel.route_snapshots.filter(
            change_request__status='approved', change_request__application='preparing'
        ).exists()
        travel.planning_status = (
            'preparing'
            if pending
            else 'ready'
            if snapshot and snapshot.state == 'ready' and snapshot.revision == travel.revision
            else 'blocked'
        )
        travel.save(update_fields=['planning_status'])


def fail_application(request):
    request.application = 'failed'
    request.save(update_fields=['application'])
    request.seat_reservations.filter(status='held').update(status='released', closed_at=timezone.now())
    for snapshot in request.route_snapshots.select_related('travel'):
        restore_previous(snapshot.travel)
    notify(
        recipients=[request.requested_by_id, request.response.eligibility.day.route_group.company.user_id],
        kind='request',
        resource_type='request',
        resource_id=request.pk,
        key=f'request:{request.pk}:failed',
        status='failed',
    )


@transaction.atomic
def request_change(*, actor_id, eligibility_id, leg, proposed_service_id, expected_revision):
    company, eligibility = eligibility_access(eligibility_id, actor_id)
    require(leg in ('outbound', 'return'), 'invalid_leg', 'Trecho inválido.')
    day, now = eligibility.day, timezone.now()
    require(
        not day.canceled_at
        and day.extension_deadline is not None
        and day.normal_deadline <= now < day.extension_deadline,
        'extension_closed',
        'A prorrogação não está aberta.',
    )
    service = selected_service(eligibility, proposed_service_id, leg)
    require(service is not None, 'invalid_service', 'Escolha um serviço para inclusão/troca.')
    response = DailyResponse.objects.filter(eligibility=eligibility).first()
    require(
        expected_revision == (response.revision if response else 0)
        or (expected_revision == 0 and response and response.answered_at is None and response.revision == 1),
        'stale_revision',
        'A resposta foi alterada.',
    )
    if response is None:
        response = DailyResponse.objects.create(eligibility=eligibility, answered_at=None)
    previous = getattr(response, f'{leg}_service_id')
    withdrawn = getattr(response, f'{leg}_withdrawn_at')
    require(
        previous != proposed_service_id or withdrawn is not None, 'same_choice', 'O serviço já é a escolha vigente.'
    )
    target = get(Travel.objects.filter(service_day=day, service=service))
    editable(target)
    for participant in eligibility.participations.filter(leg=leg, status__in=['allocated', 'on_board']).exclude(
        travel__status='canceled'
    ):
        editable(participant.travel)
    old = (
        response.change_requests
        .filter(leg=leg, status__in=['pending', 'approved'])
        .exclude(application='applied')
        .first()
    )
    if old:
        if old.proposed_service_id == proposed_service_id and old.application != 'failed':
            return old
        supersede_request(old, now=now)
    request = DailyChangeRequest.objects.create(
        response=response,
        leg=leg,
        proposed_service=service,
        expected_response_revision=response.revision,
        previous_choice_snapshot={'service_id': previous, 'withdrawn_at': withdrawn.isoformat() if withdrawn else None},
        requested_by_id=actor_id,
        created_at=now,
        expires_at=day.extension_deadline,
    )
    notify(
        recipients=[company.user_id],
        kind='request',
        resource_type='request',
        resource_id=request.pk,
        key=f'request:{request.pk}:pending',
        status='pending',
    )
    return request


def request_access(request_id, actor_id, *, company_only):
    initial = get(DailyChangeRequest.objects.all(), pk=request_id)
    company, _ = eligibility_access(initial.response.eligibility_id, actor_id, company_only=company_only)
    request = get(DailyChangeRequest.objects.select_for_update(), pk=request_id)
    return company, request


@transaction.atomic
def decide_request(*, actor_id, request_id, approve, reason=''):
    company, request = request_access(request_id, actor_id, company_only=True)
    company_actor(company, actor_id)
    require(
        isinstance(approve, bool) and isinstance(reason, str) and len(reason) <= 500,
        'invalid_decision',
        'Decisão ou motivo inválido.',
    )
    status = 'approved' if approve else 'rejected'
    if request.status == status:
        return request
    now = timezone.now()
    require(request.status == 'pending', 'request_not_pending', 'O pedido não está pendente.')
    require(now < request.expires_at, 'extension_closed', 'A prorrogação terminou.')
    require(unchanged_leg(request), 'stale_revision', 'A escolha anterior foi alterada.')
    request.status, request.decided_by_id, request.decided_at, request.reason = status, actor_id, now, reason.strip()
    if approve:
        eligibility = request.response.eligibility
        selected_service(eligibility, request.proposed_service_id, request.leg)
        target = get(Travel.objects.filter(service_day=eligibility.day, service_id=request.proposed_service_id))
        editable(target)
        capacity(target, additional=1)
        source = (
            eligibility.participations
            .filter(leg=request.leg, status__in=['allocated', 'on_board'])
            .exclude(travel__status='canceled')
            .first()
        )
        if source:
            editable(source.travel)
        request.application = 'preparing'
        request.save()
        SeatReservation.objects.create(request=request, travel=target, created_at=now, expires_at=request.expires_at)
        travels = {target.pk: target}
        if source:
            travels[source.travel_id] = source.travel
        for travel in sorted(travels.values(), key=lambda t: t.pk):
            prepare_route(travel, change_request=request)
    else:
        request.save()
    notify(
        recipients=[request.requested_by_id],
        kind='request',
        resource_type='request',
        resource_id=request.pk,
        key=f'request:{request.pk}:{status}',
        status=status,
    )
    return request


@transaction.atomic
def withdraw_request(*, actor_id, request_id):
    _, request = request_access(request_id, actor_id, company_only=False)
    if request.status == 'withdrawn':
        return request
    require(request.status == 'pending', 'request_not_pending', 'O pedido não está pendente.')
    supersede_request(request, now=timezone.now(), status='withdrawn')
    return request


@transaction.atomic
def apply_request(*, actor_id, request_id):
    company, request = request_access(request_id, actor_id, company_only=True)
    company_actor(company, actor_id)
    if request.application == 'applied':
        return request
    require(
        request.status == 'approved' and request.application == 'preparing',
        'request_not_preparing',
        'Não há proposta em preparação.',
    )
    require(unchanged_leg(request), 'stale_revision', 'A escolha anterior foi alterada.')
    snapshots = list(request.route_snapshots.select_related('travel').order_by('travel_id'))
    require(
        snapshots and all(s.state == 'ready' for s in snapshots),
        'route_not_ready',
        'O cálculo da proposta não está pronto.',
    )
    now = timezone.now()
    target = get(
        Travel.objects.filter(service_day=request.response.eligibility.day, service_id=request.proposed_service_id)
    )
    source_ids = set(
        request.response.eligibility.participations
        .filter(
            leg=request.leg,
            status__in=['allocated', 'on_board'],
        )
        .exclude(travel__status='canceled')
        .values_list('travel_id', flat=True)
    )
    require(
        {target.pk, *source_ids} == {snapshot.travel_id for snapshot in snapshots},
        'stale_revision',
        'As viagens envolvidas mudaram depois da aprovação.',
    )
    periods = {s.travel_id: (s.planned_start, s.planned_end) for s in snapshots}
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
        editable(travel)
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
    held = get(SeatReservation.objects.filter(request=request, travel=target, status='held'))
    capacity(target, additional=1, exclude_request_id=request.pk)
    eligibility = request.response.eligibility
    selected_service(eligibility, request.proposed_service_id, request.leg)
    for participant in eligibility.participations.filter(leg=request.leg, status__in=['allocated', 'on_board']):
        require(participant.status == 'allocated', 'already_boarded', 'O passageiro já embarcou.')
        participant.status, participant.withdrawn_at = 'withdrawn', now
        participant.save(update_fields=['status', 'withdrawn_at'])
        ParticipationEvent.objects.create(
            participation=participant,
            kind='withdrawn',
            actor_id=actor_id,
            occurred_at=now,
            operation_id=uuid5(NAMESPACE_URL, f'request:{request.pk}:transfer'),
        )
    participant, _ = TravelParticipation.objects.get_or_create(
        travel=target,
        eligibility=eligibility,
        defaults={'leg': request.leg, 'allocated_at': now},
    )
    participant.status, participant.allocated_at = 'allocated', now
    participant.withdrawn_at = participant.no_show_at = participant.boarded_at = participant.dropped_off_at = None
    participant.full_clean()
    participant.save()
    ParticipationEvent.objects.create(
        participation=participant,
        kind='allocated',
        actor_id=actor_id,
        occurred_at=now,
        operation_id=uuid5(NAMESPACE_URL, f'request:{request.pk}:allocation'),
    )
    response = request.response
    setattr(response, f'{request.leg}_service_id', request.proposed_service_id)
    setattr(response, f'{request.leg}_withdrawn_at', None)
    response.revision += 1
    response.answered_at = now
    response.save(update_fields=[f'{request.leg}_service', f'{request.leg}_withdrawn_at', 'revision', 'answered_at'])
    held.status, held.closed_at = 'consumed', now
    held.save(update_fields=['status', 'closed_at'])
    request.application, request.applied_at = 'applied', now
    request.save(update_fields=['application', 'applied_at'])
    from .routing import materialize_stops

    for snapshot in snapshots:
        travel = snapshot.travel
        travel.revision, travel.current_snapshot, travel.planning_status = snapshot.revision, snapshot, 'ready'
        travel.planned_start, travel.planned_end = snapshot.planned_start, snapshot.planned_end
        travel.save(update_fields=['revision', 'current_snapshot', 'planning_status', 'planned_start', 'planned_end'])
        materialize_stops(snapshot)
    notify(
        recipients=[request.requested_by_id, company.user_id],
        kind='request',
        resource_type='request',
        resource_id=request.pk,
        key=f'request:{request.pk}:applied',
        status='applied',
    )
    return request
