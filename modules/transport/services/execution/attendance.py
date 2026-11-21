"""Registro de presença pelo motorista e correção auditada pela empresa."""

from uuid import uuid5

from django.db import transaction
from django.utils import timezone

from modules.transport.broadcast import broadcast_presence
from modules.transport.models import ParticipationEvent, Travel, TravelParticipation
from modules.transport.services.actors import company_actor, driver_actor
from modules.transport.services.idempotency import check_idempotent_operation
from modules.transport.services.locking import lock_travel
from modules.transport.services.notifications import notify
from modules.transport.services.planning import capacity
from shared.exceptions import get, require

ATTENDANCE_TRANSITIONS = {
    ParticipationEvent.Kind.BOARDED: (TravelParticipation.Status.ALLOCATED, TravelParticipation.Status.ON_BOARD),
    ParticipationEvent.Kind.NO_SHOW: (TravelParticipation.Status.ALLOCATED, TravelParticipation.Status.NO_SHOW),
    ParticipationEvent.Kind.DROPPED_OFF: (TravelParticipation.Status.ON_BOARD, TravelParticipation.Status.DROPPED_OFF),
}

CORRECTION_EVENT_BY_STATUS = {
    TravelParticipation.Status.ALLOCATED: ParticipationEvent.Kind.ALLOCATED,
    TravelParticipation.Status.ON_BOARD: ParticipationEvent.Kind.BOARDED,
    TravelParticipation.Status.DROPPED_OFF: ParticipationEvent.Kind.DROPPED_OFF,
    TravelParticipation.Status.NO_SHOW: ParticipationEvent.Kind.NO_SHOW,
    TravelParticipation.Status.WITHDRAWN: ParticipationEvent.Kind.WITHDRAWN,
}


@transaction.atomic
def record_participation(*, actor_id, participation_id, kind, operation_id):
    initial = get(TravelParticipation.objects.all(), pk=participation_id)
    _, travel = lock_travel(initial.travel_id)
    driver_actor(travel, actor_id)
    participant = get(TravelParticipation.objects.select_for_update().filter(travel=travel), pk=participation_id)
    old = check_idempotent_operation(
        ParticipationEvent.objects,
        operation_id=operation_id,
        matches=lambda event: (
            event.participation_id == participant.pk and event.kind == kind and event.actor_id == actor_id
        ),
    )
    if old:
        return old
    require(travel.status == Travel.Status.IN_PROGRESS, 'travel_not_active', 'A viagem não está em andamento.')
    require(kind in ATTENDANCE_TRANSITIONS, 'invalid_event', 'Evento inválido.')
    previous, target = ATTENDANCE_TRANSITIONS[kind]
    require(participant.status == previous, 'invalid_transition', 'Transição de presença inválida.')
    if kind == ParticipationEvent.Kind.BOARDED:
        require(
            not TravelParticipation.objects
            .filter(
                eligibility__passenger_id=participant.eligibility.passenger_id,
                status=TravelParticipation.Status.ON_BOARD,
            )
            .exclude(pk=participant.pk)
            .exists(),
            'already_on_board',
            'O passageiro já está embarcado em outra viagem.',
        )
    now = timezone.now()
    participant.transition_to(target, now=now)
    event = ParticipationEvent.objects.create(
        participation=participant, kind=kind, actor_id=actor_id, occurred_at=now, operation_id=operation_id
    )
    broadcast_presence(travel.pk, participant.eligibility.passenger.user_id, participant.pk, target)
    return event


@transaction.atomic
def correct_participation(*, actor_id, participation_id, corrects_event_id, target_status, reason, operation_id):
    initial = get(TravelParticipation.objects.all(), pk=participation_id)
    company, travel = lock_travel(initial.travel_id)
    company_actor(company, actor_id)
    participant = get(TravelParticipation.objects.select_for_update().filter(travel=travel), pk=participation_id)
    corrected = get(ParticipationEvent.objects.filter(participation=participant), pk=corrects_event_id)
    require(isinstance(reason, str) and 0 < len(reason.strip()) <= 500, 'reason_required', 'A correção exige motivo.')
    clean_reason = reason.strip()
    require(target_status in CORRECTION_EVENT_BY_STATUS, 'invalid_event', 'Estado corrigido inválido.')
    require(
        travel.status in (Travel.Status.IN_PROGRESS, Travel.Status.FINISHED)
        and (
            travel.status != Travel.Status.FINISHED
            or target_status not in (TravelParticipation.Status.ALLOCATED, TravelParticipation.Status.ON_BOARD)
        ),
        'invalid_transition',
        'A correção não pode reabrir execução encerrada.',
    )
    old = check_idempotent_operation(
        ParticipationEvent.objects,
        operation_id=operation_id,
        matches=lambda event: (
            event.participation_id == participant.pk
            and event.actor_id == actor_id
            and event.corrects_id == corrected.pk
            and event.reason == clean_reason
            and ParticipationEvent.objects.filter(
                operation_id=uuid5(operation_id, 'corrected-state'),
                kind=CORRECTION_EVENT_BY_STATUS[target_status],
            ).exists()
        ),
        conflict_message='O identificador já foi usado em outra correção.',
    )
    if old:
        return old
    latest = participant.latest_non_correction_event()
    require(
        latest is not None and latest.pk == corrected.pk,
        'stale_event',
        'A marcação foi alterada; consulte o evento atual.',
    )
    if target_status in (TravelParticipation.Status.ALLOCATED, TravelParticipation.Status.ON_BOARD):
        response = getattr(participant.eligibility, 'response', None)
        require(
            response is None or not response.withdrawn_at_for(participant.leg),
            'leg_withdrawn',
            'A correção não pode desfazer a desistência do titular.',
        )
        if participant.status not in (TravelParticipation.Status.ALLOCATED, TravelParticipation.Status.ON_BOARD):
            capacity(travel, additional=1)
        if target_status == TravelParticipation.Status.ON_BOARD:
            require(
                not TravelParticipation.objects
                .filter(
                    eligibility__passenger_id=participant.eligibility.passenger_id,
                    status=TravelParticipation.Status.ON_BOARD,
                )
                .exclude(pk=participant.pk)
                .exists(),
                'already_on_board',
                'A correção não pode criar dois embarques simultâneos.',
            )
    require(
        target_status != TravelParticipation.Status.DROPPED_OFF
        or participant.events.filter(kind=ParticipationEvent.Kind.BOARDED).exists(),
        'boarding_missing',
        'Registre/corrija primeiro a marcação de embarque.',
    )
    now = timezone.now()
    correction = ParticipationEvent.objects.create(
        participation=participant,
        kind=ParticipationEvent.Kind.CORRECTION,
        corrects=corrected,
        actor_id=actor_id,
        reason=clean_reason,
        occurred_at=now,
        operation_id=operation_id,
    )
    participant.transition_to(target_status, now=now)
    ParticipationEvent.objects.create(
        participation=participant,
        kind=CORRECTION_EVENT_BY_STATUS[target_status],
        actor_id=actor_id,
        reason='Estado resultante da correção auditada.',
        occurred_at=now,
        operation_id=uuid5(operation_id, 'corrected-state'),
    )
    notify(
        recipients=[company.user_id, travel.driver.user_id, participant.eligibility.passenger.user_id],
        kind='operation',
        resource_type='travel',
        resource_id=travel.pk,
        key=f'correction:{operation_id}',
        status=travel.status,
    )
    return correction
