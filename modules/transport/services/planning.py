from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from modules.organizations.models import CompanyMembership
from modules.transport.models import (
    ParticipationEvent,
    RouteOptimizationJob,
    RouteSnapshot,
    SeatReservation,
    ServiceDay,
    Travel,
    TravelParticipation,
    TravelPublication,
)

from .common import (
    company_actor,
    editable,
    get,
    lock_company,
    lock_travel,
    notify,
    require,
    travel_recipients,
)


def frozen_service(travel):
    data = next(
        (s for s in travel.service_day.configuration_snapshot.get('services', []) if s['id'] == travel.service_id), None
    )
    require(data is not None, 'configuration_missing', 'A configuração congelada do serviço está ausente.')
    return data


def capacity(travel, *, additional=0, exclude_request_id=None):
    vehicle = travel.vehicle
    require(
        vehicle is not None
        and vehicle.company_id == travel.company_id
        and vehicle.status == 'active'
        and vehicle.capacity is not None
        and vehicle.capacity > 0,
        'vehicle_unavailable',
        'Veículo indisponível.',
    )
    count = travel.participations.filter(status__in=['allocated', 'on_board']).count()
    reservations = SeatReservation.objects.filter(travel=travel, status='held')
    if exclude_request_id:
        reservations = reservations.exclude(request_id=exclude_request_id)
    require(
        count + reservations.count() + additional <= vehicle.capacity, 'capacity_exceeded', 'Capacidade insuficiente.'
    )


def validate_roster(travel):
    for participant in travel.participations.filter(status='allocated').select_related(
        'eligibility__group_membership__membership'
    ):
        eligibility = participant.eligibility
        membership = eligibility.group_membership.membership
        require(
            membership.status == 'active'
            and membership.company_id == travel.company_id
            and eligibility.group_membership.ended_at is None
            and eligibility.passenger.user.is_active
            and travel.service_id in eligibility.authorized_service_ids,
            'participant_unavailable',
            'Há participante sem elegibilidade vigente.',
        )
        participant.full_clean()


def validate_designations(travel):
    require(travel.driver_id is not None, 'driver_missing', 'Selecione um motorista apto.')
    membership = get(
        CompanyMembership.objects.filter(company_id=travel.company_id, driver_id=travel.driver_id, status='active')
    )
    require(membership.driver.user.is_active, 'driver_unavailable', 'O motorista está indisponível.')
    if membership.pk != frozen_service(travel).get('driver_membership_id'):
        require(
            travel.driver_invitations.filter(driver_membership=membership, is_current=True, status='accepted').exists(),
            'invitation_not_accepted',
            'O substituto precisa aceitar o convite vigente.',
        )


def validate_agenda(travel, *, overrides=None):
    require(
        travel.driver_id is not None and travel.vehicle_id is not None,
        'designation_missing',
        'Motorista/veículo pendentes.',
    )
    data = frozen_service(travel)
    require(data.get('turnaround') is not None, 'schedule_incomplete', 'Informe a margem de agenda.')
    other_travels = (
        Travel.objects
        .filter(company_id=travel.company_id, service_day__isnull=False)
        .exclude(pk=travel.pk)
        .exclude(status='canceled')
    )
    other_travels = other_travels.filter(Q(driver_id=travel.driver_id) | Q(vehicle_id=travel.vehicle_id))
    for other in other_travels:
        other_margin = timedelta(seconds=frozen_service(other).get('turnaround') or 0)
        margin = timedelta(seconds=data['turnaround'])
        other_start, other_end = (overrides or {}).get(other.pk, (other.planned_start, other.planned_end))
        require(
            travel.planned_end + margin <= other_start or other_end + other_margin <= travel.planned_start,
            'schedule_conflict',
            'Motorista ou veículo possui conflito de agenda.',
        )


def ready_requirements(travel):
    require(
        not travel.route_snapshots.filter(
            change_request__status='approved', change_request__application='preparing'
        ).exists(),
        'proposal_pending',
        'Há alteração aprovada em preparação.',
    )
    ids = {travel.company.user_id}
    if travel.driver_id:
        ids.add(travel.driver.user_id)
    ids.update(
        travel.participations.filter(status='allocated').values_list('eligibility__passenger__user_id', flat=True)
    )
    users = list(get_user_model().objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    require(all(user.is_active for user in users), 'participant_unavailable', 'Há conta desativada na operação.')
    editable(travel)
    require(
        not travel.service_day.configuration_snapshot.get('issues'),
        'day_conflicts',
        'Resolva as pendências do atendimento.',
    )
    validate_designations(travel)
    require(
        travel.participations.filter(status='allocated').exists(),
        'no_demand',
        'Sem participantes; decida pelo cancelamento.',
    )
    capacity(travel)
    validate_roster(travel)
    validate_agenda(travel)
    snapshot = travel.current_snapshot
    require(
        snapshot is not None
        and snapshot.state == 'ready'
        and snapshot.revision == travel.revision
        and snapshot.travel_id == travel.pk,
        'route_not_ready',
        'O percurso atual não está pronto.',
    )
    snapshot.full_clean()
    require(
        snapshot.planned_start == travel.planned_start and snapshot.planned_end == travel.planned_end,
        'schedule_not_current',
        'A agenda não corresponde ao cálculo atual.',
    )
    require(
        snapshot.input_data.get('driver_id') == travel.driver_id
        and snapshot.input_data.get('vehicle_id') == travel.vehicle_id,
        'designation_not_current',
        'As designações mudaram depois do cálculo.',
    )
    frozen_ids = {p['eligibility_id'] for p in snapshot.input_data.get('participants', [])}
    require(
        frozen_ids == set(travel.participations.filter(status='allocated').values_list('eligibility_id', flat=True)),
        'roster_not_current',
        'A lista de participantes mudou depois do cálculo.',
    )


def prepare_route(travel, *, change_request=None):
    editable(travel)
    data = frozen_service(travel)
    entries = []
    for p in travel.participations.filter(status='allocated').select_related('eligibility').order_by('pk'):
        if change_request and p.eligibility_id == change_request.response.eligibility_id:
            continue
        entries.append({'eligibility_id': p.eligibility_id, 'point': p.eligibility.point_snapshot})
    if change_request and travel.service_id == change_request.proposed_service_id:
        eligibility = change_request.response.eligibility
        entries.append({'eligibility_id': eligibility.pk, 'point': eligibility.point_snapshot})
    latest = travel.route_snapshots.aggregate(value=Max('revision'))['value'] or 0
    revision = max(latest + 1, travel.revision)
    if change_request:
        revision = max(revision, travel.revision + 1)
    else:
        travel.revision = revision
    frozen = {'service': data, 'participants': entries}
    frozen.update(driver_id=travel.driver_id, vehicle_id=travel.vehicle_id)
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
    travel.planning_status = 'preparing'
    travel.save(update_fields=['revision', 'planning_status'])
    return snapshot


@transaction.atomic
def close_day(*, actor_id, day_id):
    initial = get(ServiceDay.objects.all(), pk=day_id)
    company = lock_company(initial.route_group.company_id)
    company_actor(company, actor_id)
    day = get(ServiceDay.objects.select_for_update().filter(route_group__company=company), pk=day_id)
    now = timezone.now()
    require(day.date >= timezone.localdate(now), 'past_day', 'Não prepare alocações em atendimento passado.')
    require(not day.canceled_at, 'day_canceled', 'O atendimento está cancelado.')
    require(now >= day.normal_deadline, 'normal_window_open', 'A janela normal ainda está aberta.')
    if day.configuration_snapshot.get('closed_revision') == day.revision:
        return day
    require(not day.configuration_snapshot.get('issues'), 'day_conflicts', 'Resolva as pendências do atendimento.')
    travels = list(day.travels.select_for_update().filter(status='scheduled').order_by('pk'))
    choices = {}
    for response in (e.response for e in day.eligibilities.select_related('response') if hasattr(e, 'response')):
        if response.answered_at is None:
            continue
        for leg in ('outbound', 'return'):
            service_id = getattr(response, f'{leg}_service_id')
            if service_id and not getattr(response, f'{leg}_withdrawn_at'):
                membership = response.eligibility.group_membership.membership
                require(
                    membership.status == 'active'
                    and membership.company_id == company.pk
                    and response.eligibility.group_membership.ended_at is None
                    and response.eligibility.passenger.user.is_active,
                    'participant_unavailable',
                    'Há demanda sem vínculo/grupo vigente.',
                )
                require(
                    service_id in response.eligibility.authorized_service_ids,
                    'service_not_authorized',
                    'Escolha não autorizada.',
                )
                choices.setdefault(service_id, []).append(response.eligibility)
    require(
        set(choices) <= {t.service_id for t in travels}, 'travel_missing', 'Falta viagem apta para uma escolha vigente.'
    )
    for travel in travels:
        capacity(
            travel,
            additional=sum(
                not travel.participations.filter(eligibility=e, status='allocated').exists()
                for e in choices.get(travel.service_id, [])
            ),
        )
    for travel in travels:
        for eligibility in choices.get(travel.service_id, []):
            participant, created = TravelParticipation.objects.get_or_create(
                travel=travel,
                eligibility=eligibility,
                defaults={'leg': travel.service.direction, 'allocated_at': now},
            )
            if not created and participant.status != 'allocated':
                require(
                    participant.status == 'withdrawn',
                    'participation_conflict',
                    'Participação incompatível com a alocação.',
                )
                participant.status, participant.allocated_at, participant.withdrawn_at = 'allocated', now, None
                participant.save(update_fields=['status', 'allocated_at', 'withdrawn_at'])
            if created:
                participant.full_clean()
                ParticipationEvent.objects.create(
                    participation=participant,
                    kind='allocated',
                    actor_id=actor_id,
                    occurred_at=now,
                    operation_id=uuid5(NAMESPACE_URL, f'close:{day.pk}:{day.revision}:{participant.pk}'),
                )
        if travel.participations.filter(status='allocated').exists():
            prepare_route(travel)
        else:
            travel.planning_status = 'blocked'
            travel.save(update_fields=['planning_status'])
    day.configuration_snapshot = {
        **day.configuration_snapshot,
        'closed_revision': day.revision,
        'operational_issue': None,
    }
    day.save(update_fields=['configuration_snapshot'])
    return day


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
    require(travel.planning_status == 'ready', 'planning_not_ready', 'O planejamento não está pronto.')
    ready_requirements(travel)
    publication, created = TravelPublication.objects.get_or_create(
        travel=travel,
        revision=travel.revision,
        defaults={'snapshot': travel.current_snapshot, 'published_by_id': actor_id},
    )
    travel.published_revision, travel.published_snapshot = travel.revision, travel.current_snapshot
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
    from modules.transport.models import Vehicle

    from .common import invalidate

    company, travel = lock_travel(travel_id)
    company_actor(company, actor_id)
    editable(travel)
    vehicle = get(Vehicle.objects.filter(company=company, status='active'), pk=vehicle_id)
    if travel.vehicle_id == vehicle.pk:
        return travel
    travel.vehicle = vehicle
    capacity(travel)
    data = frozen_service(travel)
    data['vehicle_id'] = vehicle.pk
    if travel.service.origin_id is None:
        from .calendar import point_data

        data['origin'] = point_data(vehicle.garage_point)
    day = travel.service_day
    day.save(update_fields=['configuration_snapshot'])
    travel.save(update_fields=['vehicle'])
    invalidate(travel)
    return travel
