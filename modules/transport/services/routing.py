"""Cálculo a partir de entradas congeladas; nunca consulta endereços de perfis."""

from django.db import transaction

from modules.transport.models import RouteStop, RouteStopParticipant
from modules.transport.models.planning import valid_coordinate_pair
from modules.transport.osrm import optimize_coordinates, route_coordinates

from .common import require


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
    require(
        service['duration'] is not None and main['duration_seconds'] <= service['duration'],
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
    """Associa IDs operacionais; proposta só ganha associação ao aplicar a transferência."""
    require(transaction.get_connection().in_atomic_block, 'transaction_required', 'É necessária uma transação.')
    for row in snapshot.stops.order_by('position'):
        metadata = row.point_snapshot.get('_operations', [])
        for item in metadata:
            participant = snapshot.travel.participations.filter(eligibility_id=item['eligibility_id']).first()
            if participant:
                RouteStopParticipant.objects.get_or_create(
                    stop=row, participation=participant, operation=item['operation']
                )


def persist_stops(snapshot, rows):
    for position, row in enumerate(rows, start=1):
        point = {
            **row['point'],
            '_operations': [{'eligibility_id': pk, 'operation': row['operation']} for pk in row['eligibilities']],
        }
        RouteStop.objects.create(snapshot=snapshot, position=position, point_snapshot=point)
    materialize_stops(snapshot)
