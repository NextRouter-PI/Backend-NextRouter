"""Cálculo a partir de entradas congeladas; nunca consulta endereços de perfis."""

from datetime import timedelta

from django.db import transaction

from modules.transport.models import RouteStop, RouteStopParticipant
from modules.transport.models.planning import valid_coordinate_pair
from modules.transport.osrm import optimize_coordinates, route_coordinates
from shared.exceptions import require


def coordinates(point):
    require(
        isinstance(point, dict) and valid_coordinate_pair([point.get('longitude'), point.get('latitude')]),
        'point_missing',
        'Falta ponto operacional válido.',
    )
    return [point['longitude'], point['latitude']]


def stop_offsets(result, node_count):
    """Segundos desde a saída até cada posição do trajeto otimizado (0 = partida).

    Sem trechos no retorno do OSRM (cache antigo), distribui a duração total por igual.
    """
    legs = result.get('leg_seconds') or []
    if len(legs) != node_count - 1:
        step = result['duration_seconds'] / max(1, node_count - 1)
        legs = [step] * (node_count - 1)
    offsets, total = [0], 0.0
    for leg in legs:
        total += leg
        offsets.append(round(total))
    return offsets


def calculate_frozen(frozen):
    service, participants = frozen['service'], frozen['participants']
    origin, destination, common = service['origin'], service['destination'], service['common']
    for point in (origin, destination, common):
        coordinates(point)
    stops = {}
    for entry in participants:
        point = entry['point']
        key = tuple(coordinates(point))
        stops.setdefault(key, {'point': point, 'eligibilities': []})['eligibilities'].append(entry['eligibility_id'])
    for point in service.get('stops', []):
        stops.setdefault(tuple(coordinates(point)), {'point': point, 'eligibilities': []})
    outbound = service['direction'] == 'outbound'
    start, end = (origin, common) if outbound else (common, destination)
    nodes = [start, *(stop['point'] for stop in stops.values()), end]
    positions = list(stops.values())
    points = [coordinates(point) for point in nodes]
    main = optimize_coordinates(points, has_fixed_end=True) if len(points) >= 3 else route_coordinates(points)
    side_points = (
        [coordinates(common), coordinates(destination)] if outbound else [coordinates(origin), coordinates(common)]
    )
    side = route_coordinates(side_points) if side_points[0] != side_points[1] else None
    ordered = [positions[index - 1] for index in main['order'][1:-1]]
    offsets = stop_offsets(main, len(nodes))
    rows = []
    all_ids = [entry['eligibility_id'] for entry in participants]
    if not outbound:
        rows.append({'point': common, 'eligibilities': all_ids, 'operation': 'board', 'offset_seconds': 0})
    rows.extend(
        {**stop, 'operation': 'board' if outbound else 'drop', 'offset_seconds': offsets[position]}
        for position, stop in enumerate(ordered, start=1)
    )
    if outbound:
        rows.append({'point': common, 'eligibilities': all_ids, 'operation': 'drop', 'offset_seconds': offsets[-1]})
    geometry = main['geometry']
    if side:
        first, second = (main, side) if outbound else (side, main)
        geometry = {
            'type': 'LineString',
            'coordinates': first['geometry']['coordinates'] + second['geometry']['coordinates'][1:],
        }
    if service['duration'] is not None:
        require(
            main['duration_seconds'] <= service['duration'],
            'duration_exceeded',
            'O percurso excede a duração planejada; revise a agenda.',
        )
    return {
        'geometry': geometry,
        'distance_meters': main['distance_meters'] + (side['distance_meters'] if side else 0),
        'duration_seconds': main['duration_seconds'] + (side['duration_seconds'] if side else 0),
        'side_duration': side['duration_seconds'] if side else 0,
        'stops': rows,
    }


def materialize_stops(snapshot):
    """Associa IDs operacionais em lote; proposta só ganha associação ao aplicar a transferência."""
    require(transaction.get_connection().in_atomic_block, 'transaction_required', 'É necessária uma transação.')
    participants_by_eligibility = {
        participant.eligibility_id: participant for participant in snapshot.travel.participations.all()
    }
    to_create: list[RouteStopParticipant] = []
    for row in snapshot.stops.order_by('position'):
        for item in row.point_snapshot.get('_operations', []):
            participant = participants_by_eligibility.get(item['eligibility_id'])
            if participant is not None:
                to_create.append(RouteStopParticipant(stop=row, participation=participant, operation=item['operation']))
    if to_create:
        RouteStopParticipant.objects.bulk_create(to_create, ignore_conflicts=True)


def persist_stops(snapshot, rows, base_time=None):
    """Grava as paradas; com base_time, cada uma guarda o horário previsto (_planned_at)."""
    require(transaction.get_connection().in_atomic_block, 'transaction_required', 'É necessária uma transação.')

    def planned(row):
        if base_time is None or row.get('offset_seconds') is None:
            return {}
        return {'_planned_at': (base_time + timedelta(seconds=row['offset_seconds'])).isoformat()}

    if rows:
        RouteStop.objects.bulk_create([
            RouteStop(
                snapshot=snapshot,
                position=position,
                point_snapshot={
                    **row['point'],
                    **planned(row),
                    '_operations': [
                        {'eligibility_id': pk, 'operation': row['operation']} for pk in row['eligibilities']
                    ],
                },
            )
            for position, row in enumerate(rows, start=1)
        ])
    materialize_stops(snapshot)
