import logging
from datetime import datetime, timedelta
from math import isfinite

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from modules.organizations.models import CompanyMembership
from modules.transport.models import Travel

from .common import active_actor, lock_travel, require
from .execution import driver_actor

logger = logging.getLogger(__name__)


@transaction.atomic
def save_location(*, actor_id, travel_id, latitude, longitude, recorded_at, max_future_skew, deliver=None):
    _, travel = lock_travel(travel_id)
    driver_actor(travel, actor_id)
    require(travel.status == 'in_progress', 'travel_not_active', 'A viagem não está em andamento.')
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
    travel.current_latitude, travel.current_longitude, travel.location_updated_at = latitude, longitude, recorded_at
    travel.save(update_fields=['current_latitude', 'current_longitude', 'location_updated_at'])
    event = {'latitude': latitude, 'longitude': longitude, 'updated_at': recorded_at.isoformat()}
    if deliver:

        def after_commit():
            if not Travel.objects.filter(pk=travel.pk, status='in_progress', location_updated_at=recorded_at).exists():
                return
            try:
                deliver(travel.pk, event)
            except Exception:
                logger.warning('location_delivery_failed travel_id=%s', travel.pk)

        transaction.on_commit(after_commit)
    return event


@transaction.atomic
def read_location(*, actor_id, travel_id):
    company, travel = lock_travel(travel_id)
    active_actor(actor_id)
    require(
        company.is_approved and not company.is_rejected and company.user.is_active,
        'company_unavailable',
        'A empresa não está apta a operar.',
    )
    require(travel.status == 'in_progress', 'travel_not_active', 'A viagem não está em andamento.')
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
