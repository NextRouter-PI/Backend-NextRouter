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
from shared.exceptions import get, require
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
