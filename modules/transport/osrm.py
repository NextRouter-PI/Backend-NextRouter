import hashlib
import json
import logging
from math import isfinite

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class OSRMError(ValueError):
    def __init__(self, message, status_code=503):
        self.status_code = status_code
        super().__init__(message)


def optimize_coordinates(coordinates, *, has_fixed_end=True):
    if not settings.OSRM_URL:
        raise OSRMError('Serviço de otimização indisponível.', status_code=503)
    min_coords = 3 if has_fixed_end else 2
    max_coords = settings.OSRM_MAX_STOPS + (2 if has_fixed_end else 1)
    if not min_coords <= len(coordinates) <= max_coords:
        raise OSRMError('Número de paradas fora do limite configurado.', status_code=400)
    if any(
        not (-180 <= lon <= 180 and -90 <= lat <= 90 and isfinite(lon) and isfinite(lat)) for lon, lat in coordinates
    ):
        raise OSRMError('Coordenadas inválidas para otimização.', status_code=400)

    fingerprint = hashlib.sha256(
        json.dumps(
            [settings.OSRM_URL, has_fixed_end, coordinates],
            separators=(',', ':'),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()
    key = f'osrm:trip:{fingerprint}'
    cached = cache.get(key)
    if cached is not None:
        return cached

    encoded = ';'.join(f'{lon},{lat}' for lon, lat in coordinates)
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
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, params=params, timeout=settings.OSRM_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.Timeout, requests.ConnectionError):
            if attempt == max_attempts - 1:
                logger.warning('osrm_unavailable reason=network')
                raise OSRMError('Serviço de rotas indisponível. Tente novamente mais tarde.', status_code=503) from None
        except (requests.RequestException, ValueError):
            logger.warning('osrm_unavailable reason=response')
            raise OSRMError('Serviço de rotas retornou erro.', status_code=502) from None

    try:
        if payload['code'] != 'Ok' or len(payload['trips']) != 1:
            raise ValueError
        waypoints = payload['waypoints']
        trip = payload['trips'][0]
        if len(waypoints) != len(coordinates):
            raise ValueError
        order = sorted(range(len(waypoints)), key=lambda index: waypoints[index]['waypoint_index'])
        if (
            {point['waypoint_index'] for point in waypoints} != set(range(len(waypoints)))
            or order[0] != 0
            or (has_fixed_end and order[-1] != len(waypoints) - 1)
            or any(point['distance'] > settings.OSRM_MAX_SNAP_DISTANCE_METERS for point in waypoints)
        ):
            raise ValueError
        distance, duration = float(trip['distance']), float(trip['duration'])
        geometry = trip['geometry']
        if not (isfinite(distance) and isfinite(duration) and distance >= 0 and duration >= 0):
            raise ValueError
        if geometry['type'] != 'LineString' or len(geometry['coordinates']) < 2:
            raise ValueError
        if any(len(point) < 2 or not all(isfinite(value) for value in point[:2]) for point in geometry['coordinates']):
            raise ValueError
    except (KeyError, TypeError, ValueError, IndexError):
        logger.warning('osrm_invalid_response')
        raise OSRMError('Serviço de rotas não conseguiu calcular um trajeto válido.', status_code=422) from None

    result = {'order': order, 'distance_meters': distance, 'duration_seconds': duration, 'geometry': geometry}
    cache.set(key, result, getattr(settings, 'OSRM_CACHE_TIMEOUT_SECONDS', 3600))
    return result
