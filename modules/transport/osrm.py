import hashlib
import json
import logging
from typing import Literal

import httpx
from django.conf import settings
from django.core.cache import cache
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, ValidationError

from shared.geo import CoordinatePair, GeoJSONLineString
from shared.http import NETWORK_RETRY_EXCEPTIONS, build_timeout, get_http_client, with_network_retry

logger = logging.getLogger(__name__)


class OSRMError(ValueError):
    def __init__(self, message, status_code=503):
        self.status_code = status_code
        super().__init__(message)


class _OSRMWaypoint(BaseModel):
    model_config = ConfigDict(extra='ignore')

    distance: FiniteFloat = Field(ge=0.0)


class _OSRMTripWaypoint(_OSRMWaypoint):
    waypoint_index: int = Field(ge=0)


class _OSRMGeometryLeg(BaseModel):
    model_config = ConfigDict(extra='ignore')

    distance: FiniteFloat = Field(ge=0.0)
    duration: FiniteFloat = Field(ge=0.0)
    geometry: GeoJSONLineString


class _OSRMRoutePayload(BaseModel):
    model_config = ConfigDict(extra='ignore')

    code: Literal['Ok']
    routes: list[_OSRMGeometryLeg] = Field(min_length=1, max_length=1)
    waypoints: list[_OSRMWaypoint] = Field(min_length=2, max_length=2)


class _OSRMTripPayload(BaseModel):
    model_config = ConfigDict(extra='ignore')

    code: Literal['Ok']
    trips: list[_OSRMGeometryLeg] = Field(min_length=1, max_length=1)
    waypoints: list[_OSRMTripWaypoint] = Field(min_length=2)


def _validate_coordinates(coordinates, *, error_message: str) -> list[CoordinatePair]:
    pairs: list[CoordinatePair] = []
    for point in coordinates:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise OSRMError(error_message, status_code=400)
        try:
            pairs.append(CoordinatePair(lon=point[0], lat=point[1]))
        except ValidationError:
            raise OSRMError(error_message, status_code=400) from None
    return pairs


def _cache_key(kind: str, payload_key: list) -> str:
    fingerprint = hashlib.sha256(json.dumps(payload_key, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    return f'osrm:{kind}:{fingerprint}'


def _fetch_osrm_json(url: str, *, params: dict, max_attempts: int) -> dict:
    timeout = settings.OSRM_TIMEOUT_SECONDS
    client = get_http_client('osrm', timeout=timeout)

    @with_network_retry(max_attempts=max_attempts)
    def _request() -> dict:
        response = client.get(url, params=params, timeout=build_timeout(timeout))
        response.raise_for_status()
        return response.json()

    return _request()


def route_coordinates(coordinates):
    """Segmento fixo de dois pontos; sem fabricar geometria quando não há paradas."""
    if not settings.OSRM_URL:
        raise OSRMError('Serviço de rotas indisponível.')
    if len(coordinates) != 2:
        raise OSRMError('Coordenadas inválidas.', status_code=400)
    pairs = _validate_coordinates(coordinates, error_message='Coordenadas inválidas.')

    key = _cache_key('route', [settings.OSRM_URL, [[p.lon, p.lat] for p in pairs]])
    cached = cache.get(key)
    if cached is not None:
        return cached

    encoded = ';'.join(f'{p.lon},{p.lat}' for p in pairs)
    url = f'{settings.OSRM_URL.rstrip("/")}/route/v1/driving/{encoded}'
    max_attempts = max(1, getattr(settings, 'OSRM_MAX_ATTEMPTS', 2))

    try:
        raw_payload = _fetch_osrm_json(
            url,
            params={'overview': 'full', 'geometries': 'geojson'},
            max_attempts=max_attempts,
        )
        payload = _OSRMRoutePayload.model_validate(raw_payload)
        if any(point.distance > settings.OSRM_MAX_SNAP_DISTANCE_METERS for point in payload.waypoints):
            raise ValueError('Snap distance exceeded.')
    except (httpx.HTTPError, ValidationError, ValueError, TypeError):
        raise OSRMError('Serviço de rotas não retornou um segmento válido.') from None

    route = payload.routes[0]
    result = {
        'order': [0, 1],
        'distance_meters': float(route.distance),
        'duration_seconds': float(route.duration),
        'geometry': {'type': route.geometry.type, 'coordinates': [list(pt) for pt in route.geometry.coordinates]},
    }
    cache.set(key, result, getattr(settings, 'OSRM_CACHE_TIMEOUT_SECONDS', 3600))
    return result


def optimize_coordinates(coordinates, *, has_fixed_end=True):
    if not settings.OSRM_URL:
        raise OSRMError('Serviço de otimização indisponível.', status_code=503)
    min_coords = 3 if has_fixed_end else 2
    max_coords = settings.OSRM_MAX_STOPS + (2 if has_fixed_end else 1)
    if not min_coords <= len(coordinates) <= max_coords:
        raise OSRMError('Número de paradas fora do limite configurado.', status_code=400)
    pairs = _validate_coordinates(coordinates, error_message='Coordenadas inválidas para otimização.')

    key = _cache_key('trip', [settings.OSRM_URL, has_fixed_end, [[p.lon, p.lat] for p in pairs]])
    cached = cache.get(key)
    if cached is not None:
        return cached

    encoded = ';'.join(f'{p.lon},{p.lat}' for p in pairs)
    url = f'{settings.OSRM_URL.rstrip("/")}/trip/v1/driving/{encoded}'
    params = {
        'roundtrip': 'false',
        'source': 'first',
        'overview': 'full',
        'geometries': 'geojson',
    }
    if has_fixed_end:
        params['destination'] = 'last'

    max_attempts = max(1, getattr(settings, 'OSRM_MAX_ATTEMPTS', 2))
    try:
        raw_payload = _fetch_osrm_json(url, params=params, max_attempts=max_attempts)
    except NETWORK_RETRY_EXCEPTIONS:
        logger.warning('osrm_unavailable reason=network')
        raise OSRMError('Serviço de rotas indisponível. Tente novamente mais tarde.', status_code=503) from None
    except (httpx.HTTPError, ValueError):
        logger.warning('osrm_unavailable reason=response')
        raise OSRMError('Serviço de rotas retornou erro.', status_code=502) from None

    try:
        payload = _OSRMTripPayload.model_validate(raw_payload)
        waypoints = payload.waypoints
        trip = payload.trips[0]
        if len(waypoints) != len(pairs):
            raise ValueError('Waypoint count mismatch.')
        order = sorted(range(len(waypoints)), key=lambda index: waypoints[index].waypoint_index)
        if (
            {point.waypoint_index for point in waypoints} != set(range(len(waypoints)))
            or order[0] != 0
            or (has_fixed_end and order[-1] != len(waypoints) - 1)
            or any(point.distance > settings.OSRM_MAX_SNAP_DISTANCE_METERS for point in waypoints)
        ):
            raise ValueError('Invalid trip ordering or snap distance.')
    except (ValidationError, ValueError, TypeError, IndexError):
        logger.warning('osrm_invalid_response')
        raise OSRMError('Serviço de rotas não conseguiu calcular um trajeto válido.', status_code=422) from None

    result = {
        'order': order,
        'distance_meters': float(trip.distance),
        'duration_seconds': float(trip.duration),
        'geometry': {'type': trip.geometry.type, 'coordinates': [list(pt) for pt in trip.geometry.coordinates]},
    }
    cache.set(key, result, getattr(settings, 'OSRM_CACHE_TIMEOUT_SECONDS', 3600))
    return result
