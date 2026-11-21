"""Configuração de rotas habituais e compartilhadas com travamento determinístico por PK."""

from django.db import transaction

from modules.organizations.models import HabitualRoute, OperationalPoint, PassengerGroupMembership
from modules.transport.services.calendar import regenerate_future_days
from modules.transport.services.locking import group_access
from shared.exceptions import get, require


def _sync_passenger_point(gm: PassengerGroupMembership, *, company, group, actor_id, lat: float, lng: float):
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
    fallback_city = group.destination.city if group.destination else 'Cidade não informada'
    fallback_state = group.destination.state if group.destination else 'SC'
    point.city = (user.city or '').strip() or fallback_city
    point.state = ((user.state or '').strip() or fallback_state).upper()[:2]
    point.cep = ''.join(ch for ch in (user.cep or '') if ch.isdigit()) or '00000000'
    point.latitude = lat
    point.longitude = lng
    point.full_clean()
    point.save()
    return point


@transaction.atomic
def configure_habitual_route(
    *, actor_id, group_id, route_id=None, name, kind=HabitualRoute.Kind.HABITUAL, passengers=None
):
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
        entries_by_id: dict[int, dict] = {}
        for entry in passengers:
            gm_id = entry['group_membership_id']
            require(gm_id not in entries_by_id, 'duplicate_passenger', 'Passageiro informado em duplicidade na rota.')
            entries_by_id[gm_id] = entry
        selected_ids = sorted(entries_by_id)

        # Libera passageiros removidos da rota em caso de edição.
        if route_id:
            PassengerGroupMembership.objects.filter(
                route_group=group, habitual_route=route, ended_at__isnull=True
            ).exclude(pk__in=selected_ids).update(habitual_route=None)

        # Adquire locks em ordem crescente de PK para evitar deadlocks concorrentes.
        locked_members = {
            gm.pk: gm
            for gm in PassengerGroupMembership.objects
            .select_for_update(of=('self',))
            .select_related('membership__passenger__user', 'transport_point')
            .filter(route_group=group, ended_at__isnull=True, membership__status='active', pk__in=selected_ids)
            .order_by('pk')
        }
        require(len(locked_members) == len(selected_ids), 'not_found', 'Recurso não encontrado.')

        for gm_id in selected_ids:
            gm = locked_members[gm_id]
            entry = entries_by_id[gm_id]
            require(
                gm.habitual_route_id in (None, route.pk),
                'passenger_already_in_route',
                'Um passageiro só pode estar vinculado a uma rota habitual.',
            )
            point = _sync_passenger_point(
                gm,
                company=company,
                group=group,
                actor_id=actor_id,
                lat=float(entry['latitude']),
                lng=float(entry['longitude']),
            )
            gm.habitual_route = route
            gm.transport_point = point
            gm.save(update_fields=['habitual_route', 'transport_point'])

        regenerate_future_days(group)

    return route
