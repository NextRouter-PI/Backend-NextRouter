import logging
from datetime import datetime, timedelta
from math import isfinite

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from modules.organizations.models import CompanyMembership
from modules.transport.broadcast import broadcast_approaching
from modules.transport.models import Notification, Travel
from shared.exceptions import DomainError, get, require
from shared.geo import distance_meters

from .actors import active_actor, driver_actor
from .notifications import notify

logger = logging.getLogger(__name__)
APPROACHING_RADIUS_METERS = 300.0


def location_cache_key(travel_id: int) -> str:
    return f'travel_location:{travel_id}'


def _notify_approaching_passengers(travel: Travel, latitude: float, longitude: float) -> None:
    waiting = list(travel.participations.filter(status='allocated').select_related('eligibility__passenger'))
    if not waiting:
        return
    prefix = f'approaching:{travel.pk}:'
    already_notified = set(
        Notification.objects.filter(
            resource_type='travel',
            resource_id=str(travel.pk),
            deduplication_key__startswith=prefix,
        ).values_list('deduplication_key', flat=True)
    )
    for participation in waiting:
        key = f'{prefix}{participation.pk}'
        if key in already_notified:
            continue
        point = participation.eligibility.point_snapshot or {}
        p_lat = point.get('latitude')
        p_lng = point.get('longitude')
        if not (type(p_lat) in (int, float) and type(p_lng) in (int, float) and isfinite(p_lat) and isfinite(p_lng)):
            continue
        distance = distance_meters(latitude, longitude, float(p_lat), float(p_lng))
        if distance <= APPROACHING_RADIUS_METERS:
            recipient_id = participation.eligibility.passenger.user_id
            notify(
                recipients=[recipient_id],
                kind='operation',
                resource_type='travel',
                resource_id=travel.pk,
                key=key,
                status='approaching',
                revision=travel.revision,
            )
            broadcast_approaching(
                travel.pk,
                recipient_id,
                participation.pk,
                round(distance),
            )
            already_notified.add(key)


@transaction.atomic
def save_location(*, actor_id, travel_id, latitude, longitude, recorded_at, max_future_skew, deliver=None):
    # Trava apenas a linha da viagem (não a empresa inteira) para não bloquear o tenant no GPS.
    travel = get(
        Travel.objects.dated().select_for_update(of=('self',)).select_related('company__user', 'driver'),
        pk=travel_id,
    )
    driver_actor(travel, actor_id)
    require(travel.status == Travel.Status.IN_PROGRESS, 'travel_not_active', 'A viagem não está em andamento.')
    require(
        travel.driver.location_consent_at is not None,
        'location_consent_required',
        'Autorize o compartilhamento da sua localização para enviar a posição da viagem.',
    )
    require(
        all(type(value) in (int, float) for value in (latitude, longitude))
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
        and all(isfinite(value) for value in (latitude, longitude)),
        'invalid_coordinates',
        'Coordenadas inválidas.',
    )
    now = timezone.now()
    require(
        isinstance(recorded_at, datetime)
        and timezone.is_aware(recorded_at)
        and isinstance(max_future_skew, timedelta)
        and max_future_skew.total_seconds() >= 0
        and now - recorded_at <= timedelta(seconds=settings.LOCATION_MAX_AGE_SECONDS)
        and recorded_at - now <= max_future_skew,
        'invalid_position_time',
        'Horário de posição inválido.',
    )
    if travel.location_updated_at:
        require(recorded_at > travel.location_updated_at, 'out_of_order', 'Posição fora de ordem.')
        require(
            (recorded_at - travel.location_updated_at).total_seconds() >= settings.LOCATION_MIN_INTERVAL_SECONDS,
            'position_rate_limited',
            'Envio de posição muito frequente.',
        )
    travel.current_latitude = latitude
    travel.current_longitude = longitude
    travel.location_updated_at = recorded_at
    travel.save(update_fields=['current_latitude', 'current_longitude', 'location_updated_at'])
    _notify_approaching_passengers(travel, latitude, longitude)
    event = {'latitude': latitude, 'longitude': longitude, 'updated_at': recorded_at.isoformat()}
    cache_timeout = max(30, settings.LOCATION_MAX_AGE_SECONDS * 2)

    def after_commit():
        if not Travel.objects.filter(
            pk=travel.pk, status=Travel.Status.IN_PROGRESS, location_updated_at=recorded_at
        ).exists():
            return
        try:
            cache.set(location_cache_key(travel.pk), event, timeout=cache_timeout)
        except Exception:
            logger.warning('location_cache_write_failed travel_id=%s', travel.pk)
        if deliver:
            try:
                deliver(travel.pk, event)
            except Exception:
                logger.warning('location_delivery_failed travel_id=%s', travel.pk)

    transaction.on_commit(after_commit)
    return event


def read_location(*, actor_id, travel_id):
    """Leitura pura sem lock de escrita: valida autorização e lê cache Redis com fallback no banco."""
    travel = get(Travel.objects.dated().select_related('company__user', 'driver'), pk=travel_id)
    company = travel.company
    active_actor(actor_id)
    require(
        company.is_operational,
        'company_unavailable',
        'A empresa não está apta a operar.',
    )
    require(travel.status == Travel.Status.IN_PROGRESS, 'travel_not_active', 'A viagem não está em andamento.')
    participant = travel.participations.filter(
        eligibility__passenger__user_id=actor_id,
        status__in=['allocated', 'on_board'],
        eligibility__group_membership__membership__status='active',
        eligibility__group_membership__ended_at=None,
    ).exists()
    require(
        actor_id == company.user_id
        or (
            travel.driver_id
            and actor_id == travel.driver.user_id
            and CompanyMembership.objects.filter(company=company, driver_id=travel.driver_id, status='active').exists()
        )
        or participant,
        'permission_denied',
        'Acompanhamento não autorizado.',
    )

    cached = None
    try:
        cached = cache.get(location_cache_key(travel.pk))
    except Exception:
        logger.warning('location_cache_read_failed travel_id=%s', travel.pk)
    if (
        travel.location_updated_at is not None
        and isinstance(cached, dict)
        and type(cached.get('latitude')) in (int, float)
        and type(cached.get('longitude')) in (int, float)
        and isfinite(cached['latitude'])
        and isfinite(cached['longitude'])
        and isinstance(cached.get('updated_at'), str)
    ):
        updated_at = parse_datetime(cached['updated_at'])
        if updated_at is not None and timezone.is_aware(updated_at) and updated_at >= travel.location_updated_at:
            return {
                'position': {
                    'latitude': cached['latitude'],
                    'longitude': cached['longitude'],
                    'updated_at': cached['updated_at'],
                },
                'stale': (timezone.now() - updated_at).total_seconds() > settings.LOCATION_MAX_AGE_SECONDS,
            }

    if travel.location_updated_at is None:
        return {'position': None, 'stale': True}
    return {
        'position': {
            'latitude': travel.current_latitude,
            'longitude': travel.current_longitude,
            'updated_at': travel.location_updated_at.isoformat(),
        },
        'stale': (timezone.now() - travel.location_updated_at).total_seconds() > settings.LOCATION_MAX_AGE_SECONDS,
    }


def _stop_is_open(stop, is_last):
    """Parada ainda a cumprir: não tratada e com alguém para embarcar/desembarcar (a última sempre conta)."""
    if stop.handled_at:
        return False
    items = list(stop.participants.all())
    if is_last or not items:
        return True
    return any(
        (item.operation == 'board' and item.participation.status == 'allocated')
        or (item.operation == 'drop' and item.participation.status == 'on_board')
        for item in items
    )


def live_legs(travel):
    """Trechos de rua da última posição do motorista por cada parada aberta, em ordem, até o fim.

    Devolve [(parada, resultado OSRM ou None)]. O primeiro trecho muda conforme o motorista anda;
    os seguintes ficam no cache do OSRM. Levanta OSRMError se o serviço de rotas falhar.
    """
    from concurrent.futures import ThreadPoolExecutor
    from itertools import pairwise

    from modules.transport.osrm import route_coordinates

    snapshot = travel.published_snapshot or travel.current_snapshot
    stops = (
        list(snapshot.stops.order_by('position').prefetch_related('participants__participation')) if snapshot else []
    )
    pending = [stop for index, stop in enumerate(stops) if _stop_is_open(stop, index == len(stops) - 1)]
    points = [[travel.current_longitude, travel.current_latitude]] + [
        [float(stop.point_snapshot['longitude']), float(stop.point_snapshot['latitude'])] for stop in pending
    ]
    pairs = [[a, b] for a, b in pairwise(points) if a != b]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(route_coordinates, pairs))
    by_pair = {tuple(map(tuple, pair)): result for pair, result in zip(pairs, results, strict=True)}
    legs = []
    for start, stop in zip(points, pending, strict=False):
        target = [float(stop.point_snapshot['longitude']), float(stop.point_snapshot['latitude'])]
        legs.append((stop, by_pair.get((tuple(start), tuple(target)))))
    return legs


def approach_route(*, actor_id, travel_id):
    """Trajeto de rua da posição atual do motorista por todas as paradas ainda abertas até o fim."""
    from modules.transport.osrm import OSRMError

    travel = get(
        Travel.objects.dated().select_related('company', 'driver', 'published_snapshot', 'current_snapshot'),
        pk=travel_id,
    )
    driver_actor(travel, actor_id)
    require(travel.status == Travel.Status.IN_PROGRESS, 'travel_not_active', 'A viagem não está em andamento.')
    require(travel.location_updated_at is not None, 'position_missing', 'Ainda não recebemos a sua localização.')
    try:
        legs = live_legs(travel)
    except OSRMError:
        raise DomainError('Serviço de rotas indisponível no momento.', code='routing_unavailable') from None
    return {
        'legs': [
            {
                'stop_id': stop.pk,
                'geometry': result['geometry'] if result else None,
                'distance_meters': result['distance_meters'] if result else 0,
                'duration_seconds': result['duration_seconds'] if result else 0,
            }
            for stop, result in legs
        ]
    }


def _join(results):
    coords = []
    for result in results:
        line = (result or {}).get('geometry', {}).get('coordinates') or []
        coords.extend(line[1:] if coords else line)
    return {'type': 'LineString', 'coordinates': coords} if len(coords) >= 2 else None


def passenger_route(*, actor_id, participation_id):
    """Para o próprio passageiro: o caminho de rua do motorista até ele e dele até o destino.

    Só traçado (sem paradas nem nomes de outros passageiros). Antes do embarque: posição do
    motorista até a parada de embarque, e dali até a de desembarque. A bordo: posição até o desembarque.
    Sem viagem em andamento, posição ou serviço de rotas, devolve os dois vazios (o app mostra o planejado).
    """
    from modules.transport.models import TravelParticipation
    from modules.transport.osrm import OSRMError

    participation = get(
        TravelParticipation.objects.select_related(
            'eligibility__passenger', 'travel__published_snapshot', 'travel__current_snapshot'
        ),
        pk=participation_id,
    )
    require(
        participation.eligibility.passenger.user_id == actor_id,
        'permission_denied',
        'Somente o próprio passageiro vê este caminho.',
    )
    empty = {'to_me': None, 'to_destination': None}
    travel = participation.travel
    if (
        travel.status != Travel.Status.IN_PROGRESS
        or travel.location_updated_at is None
        or participation.status not in ('allocated', 'on_board')
    ):
        return empty
    try:
        legs = live_legs(travel)
    except OSRMError:
        return empty
    mine = {
        item.operation: item.stop_id
        for stop, _ in legs
        for item in stop.participants.all()
        if item.participation_id == participation.pk
    }
    stop_ids = [stop.pk for stop, _ in legs]
    results = [result for _, result in legs]
    drop = mine.get('drop')
    end = stop_ids.index(drop) + 1 if drop in stop_ids else len(stop_ids)
    board = mine.get('board') if participation.status == 'allocated' else None
    if board in stop_ids:
        cut = stop_ids.index(board) + 1
        return {'to_me': _join(results[:cut]), 'to_destination': _join(results[cut:end])}
    return {'to_me': None, 'to_destination': _join(results[:end])}
