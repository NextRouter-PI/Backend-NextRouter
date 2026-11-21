from uuid import uuid5

from django.db import transaction
from django.utils import timezone

from modules.transport.models import (
    DailyChangeRequest,
    ParticipationEvent,
    RouteStop,
    ServiceDay,
    Travel,
    TravelParticipation,
)

from .common import (
    active_actor,
    company_actor,
    get,
    lock_company,
    lock_travel,
    membership_for,
    notify,
    require,
    travel_recipients,
)
from .planning import capacity, ready_requirements


def driver_actor(travel, actor_id):
    active_actor(actor_id)
    require(
        travel.driver_id is not None and travel.driver.user_id == actor_id,
        'permission_denied',
        'Somente o motorista designado pode executar esta ação.',
    )
    require(
        travel.company.is_operational,
        'company_unavailable',
        'A empresa não está apta a operar.',
    )
    membership_for(travel.company, driver_id=travel.driver_id)


@transaction.atomic
def start_travel(*, actor_id, travel_id, expected_revision):
    _, travel = lock_travel(travel_id)
    driver_actor(travel, actor_id)
    require(travel.revision == expected_revision, 'stale_revision', 'A viagem foi alterada.')
    if travel.status == 'in_progress':
        return travel
    require(
        travel.is_published_current,
        'publication_outdated',
        'A revisão atual precisa estar publicada.',
    )
    require(
        travel.planning_status == Travel.PlanningStatus.READY, 'planning_not_ready', 'O planejamento não está pronto.'
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
    if travel.status == 'finished':
        return travel
    require(travel.status == 'in_progress', 'travel_not_active', 'A viagem não está em andamento.')
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
    from modules.transport.broadcast import close_travel_after_commit

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


def _cancel(travel, actor_id):
    if travel.status == 'canceled':
        return travel
    require(travel.status == 'scheduled', 'execution_started', 'Não cancele viagem já iniciada.')
    from .requests import supersede_request

    for request in DailyChangeRequest.objects.filter(
        response__eligibility__day_id=travel.service_day_id, proposed_service_id=travel.service_id, status='pending'
    ):
        supersede_request(request, now=timezone.now())
    for snapshot in travel.route_snapshots.filter(change_request__application='preparing').select_related(
        'change_request'
    ):
        if snapshot.change_request.status == 'approved':
            supersede_request(snapshot.change_request, now=timezone.now())
    travel.route_snapshots.filter(state='pending').update(state='superseded')
    for snapshot in travel.route_snapshots.all():
        snapshot.optimization_jobs.filter(status__in=['pending', 'running']).update(
            status='failed',
            error='travel_canceled',
            claim_token=None,
            claim_expires_at=None,
        )
    travel.driver_invitations.filter(status='pending').update(
        status='revoked', closed_at=timezone.now(), is_current=False
    )
    travel.mark_canceled()
    notify(
        recipients=travel_recipients(travel),
        kind='cancellation',
        resource_type='travel',
        resource_id=travel.pk,
        key=f'travel:{travel.pk}:cancel',
        status='canceled',
    )
    return travel


@transaction.atomic
def cancel_travel(*, actor_id, travel_id):
    company, travel = lock_travel(travel_id)
    company_actor(company, actor_id)
    return _cancel(travel, actor_id)


@transaction.atomic
def cancel_day(*, actor_id, day_id, reason):
    initial = get(ServiceDay.objects.all(), pk=day_id)
    company = lock_company(initial.route_group.company_id)
    company_actor(company, actor_id)
    day = get(ServiceDay.objects.select_for_update(), pk=day_id)
    require(
        isinstance(reason, str) and 0 < len(reason.strip()) <= 500,
        'reason_required',
        'Informe o motivo do cancelamento.',
    )
    if not day.canceled_at:
        day.canceled_at, day.canceled_by_id, day.cancellation_reason = timezone.now(), actor_id, reason.strip()
        day.save(update_fields=['canceled_at', 'canceled_by', 'cancellation_reason'])
    from .requests import supersede_request

    for request in DailyChangeRequest.objects.filter(
        response__eligibility__day=day, status__in=['pending', 'approved']
    ).exclude(application='applied'):
        supersede_request(request, now=timezone.now())
    preserved = []
    for travel in day.travels.order_by('pk'):
        if travel.status in ('in_progress', 'finished'):
            preserved.append(travel.pk)
        else:
            _cancel(travel, actor_id)
    notify(
        recipients=[company.user_id, *day.eligibilities.values_list('passenger__user_id', flat=True)],
        kind='cancellation',
        resource_type='service_day',
        resource_id=day.pk,
        key=f'day:{day.pk}:cancel',
        status='canceled',
    )
    return {'day': day, 'preserved_travel_ids': preserved, 'partial': bool(preserved)}


@transaction.atomic
def cancel_date(*, actor_id, group_id, date, reason):
    """Tombstone mesmo antes de gerar viagens ou elegibilidades daquela data."""
    from modules.transport.models import ResponsePolicy

    from .configuration import group_access

    group = group_access(group_id, actor_id)
    require(date >= timezone.localdate(), 'past_date', 'Não cancele retroativamente uma data não gerada.')
    day = ServiceDay.objects.filter(route_group=group, date=date).first()
    if day is None:
        policy = get(ResponsePolicy.objects.all(), route_group=group)
        opens_at, normal_deadline, extension_deadline = policy.window_for(date)
        day = ServiceDay.objects.create(
            route_group=group,
            date=date,
            opens_at=opens_at,
            normal_deadline=normal_deadline,
            extension_deadline=extension_deadline,
        )
    result = cancel_day(actor_id=actor_id, day_id=day.pk, reason=reason)
    recipients = group.passenger_memberships.filter(ended_at=None, membership__status='active').values_list(
        'membership__passenger__user_id',
        flat=True,
    )
    notify(
        recipients=recipients,
        kind='cancellation',
        resource_type='service_day',
        resource_id=day.pk,
        key=f'day:{day.pk}:cancel',
        status='canceled',
    )
    return result


@transaction.atomic
def record_participation(*, actor_id, participation_id, kind, operation_id):
    initial = get(TravelParticipation.objects.all(), pk=participation_id)
    _, travel = lock_travel(initial.travel_id)
    driver_actor(travel, actor_id)
    participant = get(TravelParticipation.objects.select_for_update().filter(travel=travel), pk=participation_id)
    old = ParticipationEvent.objects.filter(operation_id=operation_id).first()
    if old:
        require(
            old.participation_id == participant.pk and old.kind == kind and old.actor_id == actor_id,
            'idempotency_conflict',
            'O identificador já foi usado em outra operação.',
        )
        return old
    require(travel.status == 'in_progress', 'travel_not_active', 'A viagem não está em andamento.')
    transitions = {
        'boarded': ('allocated', 'on_board'),
        'no_show': ('allocated', 'no_show'),
        'dropped_off': ('on_board', 'dropped_off'),
    }
    require(kind in transitions, 'invalid_event', 'Evento inválido.')
    previous, target = transitions[kind]
    require(participant.status == previous, 'invalid_transition', 'Transição de presença inválida.')
    if kind == 'boarded':
        require(
            not TravelParticipation.objects
            .filter(eligibility__passenger_id=participant.eligibility.passenger_id, status='on_board')
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
    from modules.transport.broadcast import broadcast_presence

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
    allowed = {
        'allocated': 'allocated',
        'on_board': 'boarded',
        'dropped_off': 'dropped_off',
        'no_show': 'no_show',
        'withdrawn': 'withdrawn',
    }
    require(target_status in allowed, 'invalid_event', 'Estado corrigido inválido.')
    require(
        travel.status in ('in_progress', 'finished')
        and (travel.status != 'finished' or target_status not in ('allocated', 'on_board')),
        'invalid_transition',
        'A correção não pode reabrir execução encerrada.',
    )
    old = ParticipationEvent.objects.filter(operation_id=operation_id).first()
    if old:
        require(
            old.participation_id == participant.pk
            and old.actor_id == actor_id
            and old.corrects_id == corrected.pk
            and old.reason == reason.strip()
            and ParticipationEvent.objects.filter(
                operation_id=uuid5(operation_id, 'corrected-state'), kind=allowed[target_status]
            ).exists(),
            'idempotency_conflict',
            'O identificador já foi usado em outra correção.',
        )
        return old
    latest = participant.events.exclude(kind='correction').order_by('-pk').first()
    require(
        latest is not None and latest.pk == corrected.pk,
        'stale_event',
        'A marcação foi alterada; consulte o evento atual.',
    )
    if target_status in ('allocated', 'on_board'):
        response = getattr(participant.eligibility, 'response', None)
        require(
            response is None or not getattr(response, f'{participant.leg}_withdrawn_at'),
            'leg_withdrawn',
            'A correção não pode desfazer a desistência do titular.',
        )
        if participant.status not in ('allocated', 'on_board'):
            capacity(travel, additional=1)
        if target_status == 'on_board':
            require(
                not TravelParticipation.objects
                .filter(eligibility__passenger_id=participant.eligibility.passenger_id, status='on_board')
                .exclude(pk=participant.pk)
                .exists(),
                'already_on_board',
                'A correção não pode criar dois embarques simultâneos.',
            )
    require(
        target_status != 'dropped_off' or participant.events.filter(kind='boarded').exists(),
        'boarding_missing',
        'Registre/corrija primeiro a marcação de embarque.',
    )
    now = timezone.now()
    correction = ParticipationEvent.objects.create(
        participation=participant,
        kind='correction',
        corrects=corrected,
        actor_id=actor_id,
        reason=reason.strip(),
        occurred_at=now,
        operation_id=operation_id,
    )
    participant.transition_to(target_status, now=now)
    ParticipationEvent.objects.create(
        participation=participant,
        kind=allowed[target_status],
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


@transaction.atomic
def handle_stop(*, actor_id, stop_id, skipped=False):
    initial = get(RouteStop.objects.all(), pk=stop_id)
    _, travel = lock_travel(initial.snapshot.travel_id)
    driver_actor(travel, actor_id)
    require(
        travel.status == 'in_progress' and travel.current_snapshot_id == initial.snapshot_id,
        'route_not_current',
        'A parada não pertence ao percurso em execução.',
    )
    stop = get(RouteStop.objects.select_for_update(), pk=stop_id)
    if stop.ensure_can_handle(skipped=skipped):
        stop.mark_handled(actor_id=actor_id, now=timezone.now(), skipped=skipped)
    return stop
