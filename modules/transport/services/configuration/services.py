"""Configuração de serviços recorrentes, paradas fixas e autorizações de passageiros."""

from django.db import transaction

from modules.organizations.models import OperationalPoint, PassengerGroupMembership
from modules.organizations.services.errors import MembershipError
from modules.transport.models import PassengerServiceAuthorization, RecurringService, RecurringServiceStop
from modules.transport.services.calendar import regenerate_future_days
from modules.transport.services.locking import group_access
from shared.exceptions import get, require

SERVICE_ALLOWED_FIELDS = frozenset({
    'name',
    'direction',
    'is_shared',
    'weekdays',
    'target_time',
    'valid_from',
    'valid_until',
    'driver_membership_id',
    'vehicle_id',
    'origin_id',
    'destination_id',
    'planned_duration',
    'turnaround_duration',
})


@transaction.atomic
def configure_service(*, actor_id, group_id, service_id=None, **values):
    group = group_access(group_id, actor_id)
    require(not values.keys() - SERVICE_ALLOWED_FIELDS, 'protected_field', 'Campo de serviço não permitido.')
    service = (
        get(RecurringService.objects.filter(route_group=group), pk=service_id)
        if service_id
        else RecurringService(route_group=group, created_by_id=actor_id)
    )
    if service.pk and 'direction' in values:
        require(
            service.direction == values['direction'], 'immutable_direction', 'Crie outro serviço para mudar o sentido.'
        )
    for field, value in values.items():
        setattr(service, field, value)
    service.full_clean()
    if service.vehicle_id:
        require(service.vehicle.status == 'active', 'vehicle_unavailable', 'O veículo está indisponível.')
    service.save()
    regenerate_future_days(group)
    return service


def clone_service_authorizations(*, source_participation, target_participation, group) -> None:
    """Clona autorizações habituais quando apenas o ponto do passageiro muda no mesmo grupo."""
    authorizations = list(source_participation.service_authorizations.select_related('service').order_by('pk'))
    if any(
        authorization.service.route_group_id != group.pk
        or authorization.direction != authorization.service.direction
        or (authorization.is_habitual and authorization.direction != 'outbound')
        for authorization in authorizations
    ):
        raise MembershipError('As autorizações habituais são inconsistentes.', code='invalid_authorization')
    PassengerServiceAuthorization.objects.bulk_create([
        PassengerServiceAuthorization(
            participation=target_participation,
            service_id=authorization.service_id,
            direction=authorization.direction,
            is_habitual=authorization.is_habitual,
        )
        for authorization in authorizations
    ])


@transaction.atomic
def authorize_services(*, actor_id, group_membership_id, service_ids, habitual_outbound_id=None):
    initial = get(PassengerGroupMembership.objects.all(), pk=group_membership_id)
    group = group_access(initial.route_group_id, actor_id)
    participation = get(PassengerGroupMembership.objects.filter(route_group=group), pk=group_membership_id)
    require(
        participation.ended_at is None and participation.membership.status == 'active',
        'group_not_active',
        'A participação não está vigente.',
    )
    require(
        isinstance(service_ids, list)
        and all(type(pk) is int and pk > 0 for pk in service_ids)
        and len(service_ids) == len(set(service_ids)),
        'invalid_services',
        'Informe IDs de serviços sem repetição.',
    )
    services = list(RecurringService.objects.filter(route_group=group, pk__in=service_ids).order_by('pk'))
    require(len(services) == len(service_ids), 'invalid_services', 'Serviço de outro grupo ou inexistente.')
    require(
        habitual_outbound_id is None
        or any(service.pk == habitual_outbound_id and service.direction == 'outbound' for service in services),
        'invalid_habitual',
        'A ida habitual deve ser uma ida autorizada.',
    )
    desired = {(service.pk, service.direction, service.pk == habitual_outbound_id) for service in services}
    current = set(participation.service_authorizations.values_list('service_id', 'direction', 'is_habitual'))
    if current != desired:
        participation.service_authorizations.all().delete()
        PassengerServiceAuthorization.objects.bulk_create([
            PassengerServiceAuthorization(
                participation=participation, service_id=pk, direction=direction, is_habitual=habitual
            )
            for pk, direction, habitual in sorted(desired)
        ])
        regenerate_future_days(group)
    return list(participation.service_authorizations.order_by('pk'))


@transaction.atomic
def configure_stops(*, actor_id, service_id, point_ids):
    initial = get(RecurringService.objects.all(), pk=service_id)
    group = group_access(initial.route_group_id, actor_id)
    service = get(RecurringService.objects.filter(route_group=group), pk=service_id)
    if service.is_shared:
        require(
            not point_ids,
            'shared_service_no_stops',
            'Serviços compartilhados não podem ter paradas ou rotas fixas configuradas.',
        )
    require(
        isinstance(point_ids, list)
        and all(type(pk) is int and pk > 0 for pk in point_ids)
        and len(point_ids) == len(set(point_ids)),
        'invalid_points',
        'Paradas inválidas ou repetidas.',
    )
    require(
        OperationalPoint.objects.filter(company=group.company, pk__in=point_ids).count() == len(point_ids),
        'invalid_points',
        'Os pontos devem pertencer à empresa.',
    )
    if list(service.configured_stops.order_by('position').values_list('point_id', flat=True)) != point_ids:
        service.configured_stops.all().delete()
        RecurringServiceStop.objects.bulk_create([
            RecurringServiceStop(service=service, point_id=pk, position=position)
            for position, pk in enumerate(point_ids, 1)
        ])
        regenerate_future_days(group)
    return list(service.configured_stops.order_by('position'))
