"""Sincronização em lote de elegibilidades diárias e detecção de conflitos históricos."""

import hashlib
import json

from modules.organizations.models import PassengerGroupMembership
from modules.transport.models import ServiceDayEligibility

from .snapshot_builder import point_data


def _eligibility_fingerprint(eligibility_pk: int, participation_pk: int, authorized: list[int], snapshot: dict) -> str:
    payload = json.dumps([eligibility_pk, participation_pk, authorized, snapshot], sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def _active_chosen_services(eligibility: ServiceDayEligibility) -> set[int]:
    chosen = {
        participation.travel.service_id
        for participation in eligibility.participations.all()
        if participation.status in ('allocated', 'on_board')
    }
    response = getattr(eligibility, 'response', None)
    if response is not None:
        for leg in ('outbound', 'return'):
            if response.has_active_choice(leg):
                chosen.add(response.service_id_for(leg))
    return chosen


def _has_active_commitment(eligibility: ServiceDayEligibility) -> bool:
    if any(
        participation.status in ('allocated', 'on_board') and participation.travel.status != 'canceled'
        for participation in eligibility.participations.all()
    ):
        return True
    response = getattr(eligibility, 'response', None)
    return bool(response and any(response.has_active_choice(leg) for leg in ('outbound', 'return')))


def sync_day_eligibilities(day, group, services, configuration: dict) -> None:
    """Sincroniza elegibilidades do dia com prefetch e escrita em lote."""
    active_groups = list(
        PassengerGroupMembership.objects
        .filter(
            route_group=group,
            ended_at=None,
            membership__status='active',
            membership__passenger__user__is_active=True,
        )
        .select_related('membership', 'transport_point')
        .prefetch_related('service_authorizations')
        .order_by('pk')
    )
    existing_by_passenger = {
        eligibility.passenger_id: eligibility
        for eligibility in day.eligibilities.select_related('response').prefetch_related('participations__travel')
    }

    eligible_services = {service.pk for service in services}
    shared_ids = {service.pk for service in services if service.is_shared}
    current_passengers: set[int] = set()

    to_create: list[ServiceDayEligibility] = []
    to_update: list[ServiceDayEligibility] = []
    ordered_entries: list[tuple[ServiceDayEligibility, int, list[int]]] = []

    for participation in active_groups:
        passenger_id = participation.membership.passenger_id
        current_passengers.add(passenger_id)
        explicit_ids = {auth.service_id for auth in participation.service_authorizations.all()}
        authorized = (
            sorted((explicit_ids | shared_ids) & eligible_services) if explicit_ids else sorted(eligible_services)
        )
        snapshot = point_data(participation.transport_point)

        existing = existing_by_passenger.get(passenger_id)
        if existing is None:
            eligibility = ServiceDayEligibility(
                day=day,
                passenger_id=passenger_id,
                group_membership=participation,
                authorized_service_ids=authorized,
                point_snapshot=snapshot,
            )
            to_create.append(eligibility)
            ordered_entries.append((eligibility, participation.pk, authorized))
        else:
            # Não descartar escolhas, alocações ou elegibilidade histórica conflitantes.
            if _active_chosen_services(existing) - set(authorized):
                configuration['issues'].append(f'eligibility:{existing.pk}:unauthorized_choice')
            if (
                existing.group_membership_id != participation.pk
                or existing.authorized_service_ids != authorized
                or existing.point_snapshot != snapshot
            ):
                existing.group_membership = participation
                existing.authorized_service_ids = authorized
                existing.point_snapshot = snapshot
                to_update.append(existing)
            ordered_entries.append((existing, participation.pk, authorized))

    if to_create:
        ServiceDayEligibility.objects.bulk_create(to_create)
    if to_update:
        ServiceDayEligibility.objects.bulk_update(
            to_update, ['group_membership', 'authorized_service_ids', 'point_snapshot']
        )

    for eligibility, participation_pk, authorized in ordered_entries:
        configuration['eligibility_versions'].append(
            _eligibility_fingerprint(eligibility.pk, participation_pk, authorized, eligibility.point_snapshot)
        )

    for passenger_id, eligibility in sorted(existing_by_passenger.items(), key=lambda pair: pair[1].pk):
        if passenger_id in current_passengers:
            continue
        if _has_active_commitment(eligibility):
            configuration['issues'].append(f'eligibility:{eligibility.pk}:membership_changed')
