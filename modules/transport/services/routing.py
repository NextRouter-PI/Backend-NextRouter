"""Cálculo a partir de entradas congeladas; nunca consulta endereços de perfis."""

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
    rows = []
    all_ids = [entry['eligibility_id'] for entry in participants]
    if not outbound:
        rows.append({'point': common, 'eligibilities': all_ids, 'operation': 'board'})
    rows.extend({**stop, 'operation': 'board' if outbound else 'drop'} for stop in ordered)
    if outbound:
        rows.append({'point': common, 'eligibilities': all_ids, 'operation': 'drop'})
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


def persist_stops(snapshot, rows):
    require(transaction.get_connection().in_atomic_block, 'transaction_required', 'É necessária uma transação.')
    if rows:
        RouteStop.objects.bulk_create([
            RouteStop(
                snapshot=snapshot,
                position=position,
                point_snapshot={
                    **row['point'],
                    '_operations': [
                        {'eligibility_id': pk, 'operation': row['operation']} for pk in row['eligibilities']
                    ],
                },
            )
            for position, row in enumerate(rows, start=1)
        ])
    materialize_stops(snapshot)
