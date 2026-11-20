from django.db import transaction

from modules.organizations.models import (
    CompanyRouteGroup,
    HabitualRoute,
    OperationalPoint,
    PassengerGroupMembership,
)
from modules.transport.models import (
    PassengerServiceAuthorization,
    RecurringService,
    RecurringServiceStop,
    ResponsePolicy,
    Vehicle,
)

from .common import company_actor, get, lock_company, require


def group_access(group_id, actor_id):
    initial = get(CompanyRouteGroup.objects.all(), pk=group_id)
    company = lock_company(initial.company_id)
    company_actor(company, actor_id)
    return get(CompanyRouteGroup.objects.filter(company=company), pk=group_id)


@transaction.atomic
def configure_policy(*, actor_id, group_id, **values):
    group = group_access(group_id, actor_id)
    allowed = {
        'opens_days_before',
        'opens_time',
        'normal_days_before',
        'normal_time',
        'extension_days_before',
        'extension_time',
    }
    require(not values.keys() - allowed, 'protected_field', 'Campo de política não permitido.')
    policy = ResponsePolicy.objects.filter(route_group=group).first() or ResponsePolicy(route_group=group)
    for field, value in values.items():
        setattr(policy, field, value)
    policy.full_clean()
    policy.save()
    # Prazos efetivos de datas existentes são imutáveis; a política vale para novos dias.
    return policy


@transaction.atomic
def configure_service(*, actor_id, group_id, service_id=None, **values):
    group = group_access(group_id, actor_id)
    allowed = {
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
    }
    require(not values.keys() - allowed, 'protected_field', 'Campo de serviço não permitido.')
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
    from .calendar import regenerate_future_days

    regenerate_future_days(group)
    return service


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
        or any(s.pk == habitual_outbound_id and s.direction == 'outbound' for s in services),
        'invalid_habitual',
        'A ida habitual deve ser uma ida autorizada.',
    )
    desired = {(s.pk, s.direction, s.pk == habitual_outbound_id) for s in services}
    current = set(participation.service_authorizations.values_list('service_id', 'direction', 'is_habitual'))
    if current != desired:
        participation.service_authorizations.all().delete()
        PassengerServiceAuthorization.objects.bulk_create([
            PassengerServiceAuthorization(
                participation=participation, service_id=pk, direction=direction, is_habitual=habitual
            )
            for pk, direction, habitual in sorted(desired)
        ])
        from .calendar import regenerate_future_days

        regenerate_future_days(group)
    return list(participation.service_authorizations.order_by('pk'))


@transaction.atomic
def configure_point(*, actor_id, company_id, point_id=None, **values):
    company = lock_company(company_id)
    company_actor(company, actor_id)
    allowed = {
        'point_type',
        'name',
        'street',
        'number',
        'complement',
        'neighborhood',
        'city',
        'state',
        'cep',
        'latitude',
        'longitude',
    }
    require(not values.keys() - allowed, 'protected_field', 'Campo de ponto não permitido.')
    point = (
        get(OperationalPoint.objects.filter(company=company), pk=point_id)
        if point_id
        else OperationalPoint(company=company, created_by_id=actor_id)
    )
    if point.pk and 'point_type' in values and values['point_type'] != point.point_type:
        new_type = values['point_type']
        if new_type != OperationalPoint.PointType.GARAGE:
            require(
                not point.garaged_vehicles.exists(),
                'invalid_point_type',
                'Este ponto está vinculado como garagem de veículos.',
            )
        if new_type != OperationalPoint.PointType.DESTINATION:
            require(
                not point.destination_groups.exists(),
                'invalid_point_type',
                'Este ponto está vinculado como destino de grupos de atendimento.',
            )
    for field, value in values.items():
        setattr(point, field, value)
    point.full_clean()
    point.save()
    from .calendar import regenerate_future_days

    for group in company.route_groups.order_by('pk'):
        regenerate_future_days(group)
    return point


@transaction.atomic
def configure_group(*, actor_id, company_id, group_id=None, name, destination_id):
    company = lock_company(company_id)
    company_actor(company, actor_id)
    point = get(OperationalPoint.objects.filter(company=company), pk=destination_id)
    require(
        point.point_type == OperationalPoint.PointType.DESTINATION,
        'invalid_point_type',
        'O destino do grupo deve ser um ponto operacional do tipo destino.',
    )
    group = (
        get(CompanyRouteGroup.objects.filter(company=company), pk=group_id)
        if group_id
        else CompanyRouteGroup(company=company)
    )
    group.name, group.destination = name, point
    group.full_clean()
    group.save()
    from .calendar import regenerate_future_days

    regenerate_future_days(group)
    return group


@transaction.atomic
def configure_stops(*, actor_id, service_id, point_ids):
    initial = get(RecurringService.objects.all(), pk=service_id)
    group = group_access(initial.route_group_id, actor_id)
    if initial.is_shared:
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
    if list(initial.configured_stops.order_by('position').values_list('point_id', flat=True)) != point_ids:
        initial.configured_stops.all().delete()
        RecurringServiceStop.objects.bulk_create([
            RecurringServiceStop(service=initial, point_id=pk, position=position)
            for position, pk in enumerate(point_ids, 1)
        ])
        from .calendar import regenerate_future_days

        regenerate_future_days(group)
    return list(initial.configured_stops.order_by('position'))


@transaction.atomic
def configure_vehicle(*, actor_id, company_id, vehicle_id=None, **values):
    company = lock_company(company_id)
    company_actor(company, actor_id)
    require(
        not values.keys() - {'plate', 'model', 'year', 'capacity', 'status', 'garage_point_id', 'color', 'features'},
        'protected_field',
        'Campo de frota não permitido.',
    )
    vehicle = get(Vehicle.objects.filter(company=company), pk=vehicle_id) if vehicle_id else Vehicle(company=company)
    if vehicle.pk:
        require(
            not vehicle.travels.filter(status='in_progress').exists(), 'operation_in_progress', 'Veículo em operação.'
        )
    if values.get('garage_point_id') is not None:
        garage_point = get(OperationalPoint.objects.filter(company=company), pk=values['garage_point_id'])
        require(
            garage_point.point_type == OperationalPoint.PointType.GARAGE,
            'invalid_point_type',
            'O ponto selecionado para o veículo deve ser do tipo garagem.',
        )
    for field, value in values.items():
        setattr(vehicle, field, value)
    vehicle.full_clean()
    vehicle.save()
    from .calendar import regenerate_future_days
    from .common import invalidate

    for group in company.route_groups.order_by('pk'):
        regenerate_future_days(group)
    for travel in vehicle.travels.filter(service_day__isnull=False, status='scheduled').order_by('pk'):
        invalidate(travel)
    return vehicle


@transaction.atomic
def configure_habitual_route(*, actor_id, group_id, route_id=None, name, kind=HabitualRoute.Kind.HABITUAL, passengers=None):
    """Cria ou atualiza rota habitual (com passageiros e pontos ajustados) ou compartilhada (apenas nome)."""
    group = group_access(group_id, actor_id)
    company = group.company
    clean_name = str(name or '').strip()
    require(bool(clean_name), 'invalid_name', 'Informe o nome da rota.')
    require(
        kind in (HabitualRoute.Kind.HABITUAL, HabitualRoute.Kind.SHARED),
        'invalid_kind',
        'Tipo de rota inválido.',
    )

    route = (
        get(HabitualRoute.objects.filter(route_group=group), pk=route_id)
        if route_id
        else HabitualRoute(route_group=group, created_by_id=actor_id)
    )
    if route.pk and route.kind != kind:
        require(False, 'immutable_kind', 'Não é possível alterar o tipo da rota após criada.')

    route.name = clean_name
    route.kind = kind
    route.full_clean()
    route.save()

    if kind == HabitualRoute.Kind.SHARED:
        require(
            not passengers,
            'shared_route_no_passengers',
            'Rotas compartilhadas possuem apenas nome e não vinculam passageiros individuais.',
        )
        return route

    if passengers is not None:
        selected_ids = []
        seen_ids = set()
        for entry in passengers:
            gm_id = entry['group_membership_id']
            require(gm_id not in seen_ids, 'duplicate_passenger', 'Passageiro informado em duplicidade na rota.')
            seen_ids.add(gm_id)
            selected_ids.append(gm_id)

        # Libera passageiros removidos da rota em caso de edição.
        if route_id:
            PassengerGroupMembership.objects.filter(
                route_group=group, habitual_route=route, ended_at__isnull=True
            ).exclude(pk__in=selected_ids).update(habitual_route=None)

        for entry in passengers:
            gm = get(
                PassengerGroupMembership.objects.select_for_update()
                .select_related('membership__passenger__user', 'transport_point')
                .filter(route_group=group, ended_at__isnull=True, membership__status='active'),
                pk=entry['group_membership_id'],
            )
            require(
                gm.habitual_route_id in (None, route.pk),
                'passenger_already_in_route',
                'Um passageiro só pode estar vinculado a uma rota habitual.',
            )

            lat = float(entry['latitude'])
            lng = float(entry['longitude'])
            user = gm.membership.passenger.user
            point = (
                gm.transport_point
                if gm.transport_point_id and gm.transport_point.point_type == OperationalPoint.PointType.PASSENGER
                else OperationalPoint(
                    company=company,
                    created_by_id=actor_id,
                    point_type=OperationalPoint.PointType.PASSENGER,
                )
            )
            point.point_type = OperationalPoint.PointType.PASSENGER
            point.name = f'Ponto de {user.name}'[:100]
            point.street = (user.street or '').strip() or 'Logradouro não informado'
            point.number = (user.number or '').strip() or 'S/N'
            point.complement = (user.complement or '').strip()
            point.neighborhood = (user.neighborhood or '').strip() or 'Bairro não informado'
            point.city = (user.city or '').strip() or (group.destination.city if group.destination else 'Cidade não informada')
            point.state = ((user.state or '').strip() or (group.destination.state if group.destination else 'SC')).upper()[:2]
            point.cep = ''.join(ch for ch in (user.cep or '') if ch.isdigit()) or '00000000'
            point.latitude = lat
            point.longitude = lng
            point.full_clean()
            point.save()

            gm.habitual_route = route
            gm.transport_point = point
            gm.save(update_fields=['habitual_route', 'transport_point'])

        from .calendar import regenerate_future_days

        regenerate_future_days(group)

    return route
