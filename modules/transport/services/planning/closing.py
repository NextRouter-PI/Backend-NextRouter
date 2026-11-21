"""Fechamento da janela normal de respostas e preparação de snapshots de rota."""

from uuid import NAMESPACE_URL, uuid5

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from modules.transport.models import (
    ParticipationEvent,
    RouteOptimizationJob,
    RouteSnapshot,
    ServiceDay,
    Travel,
    TravelParticipation,
)
from modules.transport.services.actors import company_actor
from modules.transport.services.locking import lock_for_company
from shared.exceptions import require

from .validators import capacity, frozen_service


def prepare_route(travel: Travel, *, change_request=None) -> RouteSnapshot:
    travel.ensure_editable()
    data = frozen_service(travel)
    entries = []
    for participant in travel.participations.filter(status='allocated').select_related('eligibility').order_by('pk'):
        if change_request and participant.eligibility_id == change_request.response.eligibility_id:
            continue
        entries.append({'eligibility_id': participant.eligibility_id, 'point': participant.eligibility.point_snapshot})
    if change_request and travel.service_id == change_request.proposed_service_id:
        eligibility = change_request.response.eligibility
        entries.append({'eligibility_id': eligibility.pk, 'point': eligibility.point_snapshot})
    latest = travel.route_snapshots.aggregate(value=Max('revision'))['value'] or 0
    revision = max(latest + 1, travel.revision)
    if change_request:
        revision = max(revision, travel.revision + 1)
    else:
        travel.revision = revision
    frozen = {
        'service': data,
        'participants': entries,
        'driver_id': travel.driver_id,
        'vehicle_id': travel.vehicle_id,
    }
    snapshot = RouteSnapshot.objects.create(
        travel=travel,
        revision=revision,
        base_revision=travel.revision,
        change_request=change_request,
        input_data=frozen,
        origin=data['origin'],
        destination=data['destination'],
        created_at=timezone.now(),
    )
    RouteOptimizationJob.objects.create(snapshot=snapshot, input_revision=travel.revision, frozen_input=frozen)
    travel.planning_status = Travel.PlanningStatus.PREPARING
    travel.save(update_fields=['revision', 'planning_status'])
    return snapshot


def _collect_day_choices(day: ServiceDay, company) -> dict[int, list]:
    choices: dict[int, list] = {}
    eligibilities = day.eligibilities.select_related(
        'response',
        'group_membership__membership',
        'passenger__user',
    ).order_by('pk')
    for eligibility in eligibilities:
        response = getattr(eligibility, 'response', None)
        if response is None or response.answered_at is None:
            continue
        for leg in ('outbound', 'return'):
            if not response.has_active_choice(leg):
                continue
            service_id = response.service_id_for(leg)
            membership = eligibility.group_membership.membership
            require(
                membership.status == 'active'
                and membership.company_id == company.pk
                and eligibility.group_membership.ended_at is None
                and eligibility.passenger.user.is_active,
                'participant_unavailable',
                'Há demanda sem vínculo/grupo vigente.',
            )
            require(eligibility.authorizes(service_id), 'service_not_authorized', 'Escolha não autorizada.')
            choices.setdefault(service_id, []).append(eligibility)
    return choices


@transaction.atomic
def close_day(*, actor_id, day_id) -> ServiceDay:
    company, day = lock_for_company(
        ServiceDay.objects.all(),
        day_id,
        company_getter=lambda item: item.route_group.company_id,
        company_filter='route_group__company',
    )
    company_actor(company, actor_id)
    now = timezone.now()
    require(day.date >= timezone.localdate(now), 'past_day', 'Não prepare alocações em atendimento passado.')
    require(not day.canceled_at, 'day_canceled', 'O atendimento está cancelado.')
    require(now >= day.normal_deadline, 'normal_window_open', 'A janela normal ainda está aberta.')
    if day.configuration_snapshot.get('closed_revision') == day.revision:
        return day
    require(not day.configuration_snapshot.get('issues'), 'day_conflicts', 'Resolva as pendências do atendimento.')

    travels = list(
        day.travels
        .select_for_update(of=('self',))
        .select_related('service', 'vehicle')
        .filter(status='scheduled')
        .order_by('pk')
    )
    choices = _collect_day_choices(day, company)
    require(
        set(choices) <= {travel.service_id for travel in travels},
        'travel_missing',
        'Falta viagem apta para uma escolha vigente.',
    )

    existing_by_travel: dict[int, dict[int, TravelParticipation]] = {}
    for travel in travels:
        by_eligibility = {p.eligibility_id: p for p in travel.participations.all()}
        existing_by_travel[travel.pk] = by_eligibility
        additional = sum(
            1
            for eligibility in choices.get(travel.service_id, [])
            if eligibility.pk not in by_eligibility or by_eligibility[eligibility.pk].status != 'allocated'
        )
        capacity(travel, additional=additional)

    events_to_create: list[ParticipationEvent] = []
    for travel in travels:
        by_eligibility = existing_by_travel[travel.pk]
        for eligibility in choices.get(travel.service_id, []):
            participant = by_eligibility.get(eligibility.pk)
            if participant is None:
                participant = TravelParticipation(
                    travel=travel,
                    eligibility=eligibility,
                    leg=travel.service.direction,
                    allocated_at=now,
                )
                participant.full_clean()
                participant.save()
                by_eligibility[eligibility.pk] = participant
                events_to_create.append(
                    ParticipationEvent(
                        participation=participant,
                        kind=ParticipationEvent.Kind.ALLOCATED,
                        actor_id=actor_id,
                        occurred_at=now,
                        operation_id=uuid5(NAMESPACE_URL, f'close:{day.pk}:{day.revision}:{participant.pk}'),
                    )
                )
            elif participant.status != TravelParticipation.Status.ALLOCATED:
                require(
                    participant.status == TravelParticipation.Status.WITHDRAWN,
                    'participation_conflict',
                    'Participação incompatível com a alocação.',
                )
                participant.status = TravelParticipation.Status.ALLOCATED
                participant.allocated_at = now
                participant.withdrawn_at = None
                participant.save(update_fields=['status', 'allocated_at', 'withdrawn_at'])

        if any(p.status == TravelParticipation.Status.ALLOCATED for p in by_eligibility.values()):
            prepare_route(travel)
        else:
            travel.planning_status = Travel.PlanningStatus.BLOCKED
            travel.save(update_fields=['planning_status'])

    if events_to_create:
        ParticipationEvent.objects.bulk_create(events_to_create)

    day.configuration_snapshot = {
        **day.configuration_snapshot,
        'closed_revision': day.revision,
        'operational_issue': None,
    }
    day.save(update_fields=['configuration_snapshot'])
    return day
