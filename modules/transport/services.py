import logging
from datetime import timedelta
from math import isfinite

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from modules.transport.models.path import Path
from modules.transport.models.travel import Travel
from shared.geocoding import geocode_address

logger = logging.getLogger(__name__)


class LocationRejected(ValueError):
    def __init__(self, message, status_code=400):
        self.status_code = status_code
        super().__init__(message)


@transaction.atomic
def save_travel_location(travel_id, user_id, latitude, longitude, recorded_at=None):
    travel = Travel.objects.select_for_update().select_related('driver').get(pk=travel_id)
    if travel.driver.user_id != user_id or not travel.driver.is_approved:
        raise LocationRejected('Apenas o motorista designado pode enviar a localização.', 403)
    if travel.status != Travel.Status.IN_PROGRESS:
        raise LocationRejected('Esta viagem não está em andamento.')
    if not all(isfinite(value) for value in (latitude, longitude)) or not (
        -90 <= latitude <= 90 and -180 <= longitude <= 180
    ):
        raise LocationRejected('Coordenadas inválidas.')

    now = timezone.now()
    # shortcut: sem recorded_at usa hora de recebimento; exigir o campo após atualizar os clientes.
    observed_at = recorded_at or now
    if (
        not timezone.is_aware(observed_at)
        or observed_at > now + timedelta(seconds=5)
        or observed_at < now - timedelta(seconds=settings.LOCATION_MAX_AGE_SECONDS)
    ):
        raise LocationRejected('Posição antiga ou com horário inválido.')
    if travel.location_updated_at and observed_at <= travel.location_updated_at:
        raise LocationRejected('Posição fora de ordem.')
    if travel.location_updated_at and observed_at - travel.location_updated_at < timedelta(
        seconds=settings.LOCATION_MIN_INTERVAL_SECONDS
    ):
        raise LocationRejected('Envio de localização muito frequente.', 429)

    travel.current_latitude = latitude
    travel.current_longitude = longitude
    travel.location_updated_at = observed_at
    travel.save(update_fields=['current_latitude', 'current_longitude', 'location_updated_at'])
    event = {
        'type': 'location_update',
        'latitude': latitude,
        'longitude': longitude,
        'updated_at': observed_at.isoformat(),
    }

    def broadcast():
        try:
            async_to_sync(get_channel_layer().group_send)(f'travel_{travel.pk}', event)
        except (OSError, TimeoutError):
            logger.exception('location_delivery_failed travel_id=%s', travel.pk)

    transaction.on_commit(broadcast, robust=True)
    return event


def ensure_route_group_geocoded(route_group):
    """
    Geocodifica o CEP em comum do grupo de rota, se ainda não tiver coordenadas.
    Usado para ter um ponto de referência central ao calcular rotas/paradas.
    """
    if route_group.reference_latitude is not None or not route_group.common_cep:
        return route_group

    latitude, longitude = geocode_address(cep=route_group.common_cep)
    if latitude is not None:
        from django.utils import timezone

        route_group.reference_latitude = latitude
        route_group.reference_longitude = longitude
        route_group.geocoded_at = timezone.now()
        route_group.save(update_fields=['reference_latitude', 'reference_longitude', 'geocoded_at'])

    return route_group


def ensure_default_path(route_group):
    """
    Garante que o grupo de rota tenha um trajeto (Path) para acumular as paradas
    dos passageiros/motoristas automaticamente.
    """
    path, _ = Path.objects.get_or_create(
        route_group=route_group,
        name='Trajeto automático',
        defaults={'points': []},
    )
    return path


def sync_stop_for_user(route_group, user, *, label=None):
    """
    Adiciona (ou atualiza) uma parada no trajeto automático do grupo de rota
    com a localização geocodificada do usuário. Não faz nada se o usuário
    ainda não tiver latitude/longitude (endereço incompleto ou não geocodificado).
    """
    if user.latitude is None or user.longitude is None:
        return None

    path = ensure_default_path(route_group)

    address_parts = [part for part in (user.street, user.number, user.neighborhood, user.city, user.state) if part]
    stop = {
        'user_id': user.id,
        'label': label or user.name,
        'latitude': user.latitude,
        'longitude': user.longitude,
        'address': ', '.join(address_parts),
    }

    points = [point for point in (path.points or []) if point.get('user_id') != user.id]
    points.append(stop)

    path.points = points
    path.save(update_fields=['points'])
    return path
