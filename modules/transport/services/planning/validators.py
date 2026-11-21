"""Validações de planejamento operacional: capacidade, elenco, designações, agenda e prontidão."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q

from modules.organizations.models import CompanyMembership
from modules.transport.models import RouteSnapshot, Travel
from shared.exceptions import get, require


def frozen_service(travel: Travel) -> dict:
    data = travel.service_day.service_config(travel.service_id)
    require(data is not None, 'configuration_missing', 'A configuração congelada do serviço está ausente.')
    return data


def capacity(travel: Travel, *, additional: int = 0, exclude_request_id=None) -> None:
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
    occupied = travel.occupied_seat_count(exclude_request_id=exclude_request_id)
    require(occupied + additional <= vehicle.capacity, 'capacity_exceeded', 'Capacidade insuficiente.')


def validate_roster(travel: Travel) -> None:
    for participant in travel.participations.filter(status='allocated').select_related(
        'eligibility__group_membership__membership',
        'eligibility__passenger__user',
    ):
        eligibility = participant.eligibility
        membership = eligibility.group_membership.membership
        require(
            membership.status == 'active'
            and membership.company_id == travel.company_id
            and eligibility.group_membership.ended_at is None
            and eligibility.passenger.user.is_active
            and eligibility.authorizes(travel.service_id),
            'participant_unavailable',
            'Há participante sem elegibilidade vigente.',
        )
        participant.full_clean()


def validate_designations(travel: Travel) -> None:
    require(travel.driver_id is not None, 'driver_missing', 'Selecione um motorista apto.')
    membership = get(
        CompanyMembership.objects.select_related('driver__user').filter(
            company_id=travel.company_id, driver_id=travel.driver_id, status='active'
        )
    )
    require(membership.driver.user.is_active, 'driver_unavailable', 'O motorista está indisponível.')
    if membership.pk != frozen_service(travel).get('driver_membership_id'):
        require(
            travel.driver_invitations.filter(driver_membership=membership, is_current=True, status='accepted').exists(),
            'invitation_not_accepted',
            'O substituto precisa aceitar o convite vigente.',
        )


def validate_agenda(travel: Travel, *, overrides=None) -> None:
    require(
        travel.driver_id is not None and travel.vehicle_id is not None,
        'designation_missing',
        'Motorista/veículo pendentes.',
    )
    data = frozen_service(travel)
    margin = timedelta(seconds=data.get('turnaround') or 0)
    day_date = travel.service_day.date
    date_window = Q(service_day__date__range=(day_date - timedelta(days=1), day_date + timedelta(days=1)))
    if overrides:
        date_window |= Q(pk__in=overrides)
    other_travels = (
        Travel.objects
        .dated()
        .not_canceled()
        .filter(company_id=travel.company_id)
        .filter(date_window)
        .filter(Q(driver_id=travel.driver_id) | Q(vehicle_id=travel.vehicle_id))
        .exclude(pk=travel.pk)
        .select_related('service_day')
    )
    for other in other_travels:
        other_margin = timedelta(seconds=frozen_service(other).get('turnaround') or 0)
        other_start, other_end = (overrides or {}).get(other.pk, (other.planned_start, other.planned_end))
        require(
            travel.planned_end + margin <= other_start or other_end + other_margin <= travel.planned_start,
            'schedule_conflict',
            'Motorista ou veículo possui conflito de agenda.',
        )


def ready_requirements(travel: Travel) -> None:
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
    travel.ensure_editable()
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
        and snapshot.state == RouteSnapshot.State.READY
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
