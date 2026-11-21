"""Ciclo de vida de pedidos de alteração diária (prorrogação): abertura, decisão, retirada e falha."""

from django.db import transaction
from django.utils import timezone

from modules.transport.models import DailyChangeRequest, DailyResponse, SeatReservation, Travel
from modules.transport.services.actors import company_actor
from modules.transport.services.demand import eligibility_access, selected_service
from modules.transport.services.notifications import notify
from modules.transport.services.planning import capacity, prepare_route
from shared.exceptions import get, require


def unchanged_leg(request: DailyChangeRequest) -> bool:
    return request.is_leg_unchanged()


def supersede_request(request: DailyChangeRequest, *, now, status: str = DailyChangeRequest.Status.SUPERSEDED) -> None:
    request.supersede(now=now, status=status)


def restore_previous(travel: Travel) -> None:
    travel.restore_previous_planning_status()


def fail_application(request: DailyChangeRequest) -> None:
    request.mark_failed()
    request.seat_reservations.filter(status='held').update(status='released', closed_at=timezone.now())
    for snapshot in request.route_snapshots.select_related('travel').order_by('travel_id'):
        snapshot.travel.restore_previous_planning_status()
    notify(
        recipients=[request.requested_by_id, request.response.eligibility.day.route_group.company.user_id],
        kind='request',
        resource_type='request',
        resource_id=request.pk,
        key=f'request:{request.pk}:failed',
        status='failed',
    )


def request_access(request_id, actor_id, *, company_only: bool):
    initial = get(DailyChangeRequest.objects.all(), pk=request_id)
    company, _ = eligibility_access(initial.response.eligibility_id, actor_id, company_only=company_only)
    request = get(DailyChangeRequest.objects.select_for_update(), pk=request_id)
    return company, request


@transaction.atomic
def request_change(*, actor_id, eligibility_id, leg, proposed_service_id, expected_revision):
    company, eligibility = eligibility_access(eligibility_id, actor_id)
    require(leg in ('outbound', 'return'), 'invalid_leg', 'Trecho inválido.')
    day, now = eligibility.day, timezone.now()
    require(day.is_extension_window_open(now=now), 'extension_closed', 'A prorrogação não está aberta.')
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
    previous = response.service_id_for(leg)
    withdrawn = response.withdrawn_at_for(leg)
    require(
        previous != proposed_service_id or withdrawn is not None, 'same_choice', 'O serviço já é a escolha vigente.'
    )
    target = get(Travel.objects.filter(service_day=day, service=service))
    target.ensure_editable()
    for participant in eligibility.participations.active_occupancy().filter(leg=leg).exclude(travel__status='canceled'):
        participant.travel.ensure_editable()
    old = response.change_requests.open_requests().filter(leg=leg).first()
    if old:
        if old.proposed_service_id == proposed_service_id and old.application != DailyChangeRequest.Application.FAILED:
            return old
        old.supersede(now=now)
    request = DailyChangeRequest.objects.create(
        response=response,
        leg=leg,
        proposed_service=service,
        expected_response_revision=response.revision,
        previous_choice_snapshot=response.leg_snapshot(leg),
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


@transaction.atomic
def decide_request(*, actor_id, request_id, approve, reason=''):
    company, request = request_access(request_id, actor_id, company_only=True)
    company_actor(company, actor_id)
    require(
        isinstance(approve, bool) and isinstance(reason, str) and len(reason) <= 500,
        'invalid_decision',
        'Decisão ou motivo inválido.',
    )
    status = DailyChangeRequest.Status.APPROVED if approve else DailyChangeRequest.Status.REJECTED
    if request.status == status:
        return request
    now = timezone.now()
    require(request.status == DailyChangeRequest.Status.PENDING, 'request_not_pending', 'O pedido não está pendente.')
    require(now < request.expires_at, 'extension_closed', 'A prorrogação terminou.')
    require(request.is_leg_unchanged(), 'stale_revision', 'A escolha anterior foi alterada.')
    request.status = status
    request.decided_by_id = actor_id
    request.decided_at = now
    request.reason = reason.strip()
    if approve:
        eligibility = request.response.eligibility
        selected_service(eligibility, request.proposed_service_id, request.leg)
        target = get(Travel.objects.filter(service_day=eligibility.day, service_id=request.proposed_service_id))
        target.ensure_editable()
        capacity(target, additional=1)
        source = (
            eligibility.participations
            .active_occupancy()
            .filter(leg=request.leg)
            .exclude(travel__status='canceled')
            .first()
        )
        if source:
            source.travel.ensure_editable()
        request.application = DailyChangeRequest.Application.PREPARING
        request.save()
        SeatReservation.objects.create(request=request, travel=target, created_at=now, expires_at=request.expires_at)
        travels = {target.pk: target}
        if source:
            travels[source.travel_id] = source.travel
        for travel in sorted(travels.values(), key=lambda item: item.pk):
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
    if request.status == DailyChangeRequest.Status.WITHDRAWN:
        return request
    require(request.status == DailyChangeRequest.Status.PENDING, 'request_not_pending', 'O pedido não está pendente.')
    request.supersede(now=timezone.now(), status=DailyChangeRequest.Status.WITHDRAWN)
    return request
