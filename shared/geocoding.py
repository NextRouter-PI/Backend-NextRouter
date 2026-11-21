import logging

import httpx
from django.conf import settings
from django.core.cache import cache
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, TypeAdapter, ValidationError

from shared.geo import CoordinatePair
from shared.http import NETWORK_RETRY_EXCEPTIONS, build_timeout, get_http_client, with_network_retry

logger = logging.getLogger(__name__)

BRASILAPI_CEP_V2_URL = 'https://brasilapi.com.br/api/cep/v2/{cep}'
_CEP_NOT_FOUND = '__cep_not_found__'


class GeocodingError(ValueError):
    pass


class _BrasilAPICoordinates(BaseModel):
    model_config = ConfigDict(extra='ignore')

    latitude: str | float | int | None = None
    longitude: str | float | int | None = None


class _BrasilAPILocation(BaseModel):
    model_config = ConfigDict(extra='ignore')

    coordinates: _BrasilAPICoordinates | None = None


class _BrasilAPICepPayload(BaseModel):
    model_config = ConfigDict(extra='ignore')

    state: str | None = None
    city: str | None = None
    neighborhood: str | None = None
    street: str | None = None
    location: _BrasilAPILocation | None = None

    def extract_coordinates(self) -> tuple[float | None, float | None]:
        coords = self.location.coordinates if self.location else None
        if not coords or coords.latitude in (None, '') or coords.longitude in (None, ''):
            return None, None
        try:
            pair = CoordinatePair(lon=float(coords.longitude), lat=float(coords.latitude))
        except (TypeError, ValueError, ValidationError):
            return None, None
        return pair.lat, pair.lon


class _NominatimResult(BaseModel):
    model_config = ConfigDict(extra='ignore')

    lat: FiniteFloat = Field(ge=-90.0, le=90.0)
    lon: FiniteFloat = Field(ge=-180.0, le=180.0)


_NOMINATIM_LIST_ADAPTER = TypeAdapter(list[_NominatimResult])


def lookup_cep_brasilapi(cep, *, timeout=None, raise_on_error=False):
    """Consulta endereço e coordenadas aproximadas pela BrasilAPI CEP v2 com cache e pool HTTP.

    Retorna dict {cep, state, city, neighborhood, street, latitude, longitude}
    ou None se não encontrado. Quando `raise_on_error=True`, levanta `GeocodingError`
    em falhas de rede/upstream para diferenciar 404 de 503.
    """
    clean_cep = ''.join(ch for ch in str(cep or '') if ch.isdigit())
    if len(clean_cep) != 8:
        return None

    cache_key = f'geocoding:cep:{clean_cep}'
    cached = cache.get(cache_key)
    if cached is not None:
        return None if cached == _CEP_NOT_FOUND else cached

    req_timeout = timeout or getattr(settings, 'GEOCODING_TIMEOUT_SECONDS', 5)
    hit_ttl = getattr(settings, 'CEP_CACHE_HIT_TTL_SECONDS', 86400)
    miss_ttl = getattr(settings, 'CEP_CACHE_MISS_TTL_SECONDS', 60)
    client = get_http_client('geocoding', timeout=req_timeout)
    try:
        response = client.get(BRASILAPI_CEP_V2_URL.format(cep=clean_cep), timeout=build_timeout(req_timeout))
        if response.status_code == 404:
            cache.set(cache_key, _CEP_NOT_FOUND, miss_ttl)
            return None
        response.raise_for_status()
        payload = _BrasilAPICepPayload.model_validate(response.json())
    except (httpx.HTTPError, ValidationError, ValueError) as exc:
        logger.warning('brasilapi_cep_failed reason=%s', type(exc).__name__)
        if raise_on_error:
            raise GeocodingError('Serviço de consulta de CEP temporariamente indisponível.') from None
        return None

    latitude, longitude = payload.extract_coordinates()
    result = {
        'cep': clean_cep,
        'state': (payload.state or '').strip().upper()[:2],
        'city': (payload.city or '').strip(),
        'neighborhood': (payload.neighborhood or '').strip(),
        'street': (payload.street or '').strip(),
        'latitude': latitude,
        'longitude': longitude,
    }
    cache.set(cache_key, result, hit_ttl)
    return result


def geocode_address(*, street='', number='', neighborhood='', city='', state='', cep='', strict=False):
    """
    Converte um endereço em coordenadas (latitude, longitude) usando Nominatim/OpenStreetMap.

    Retorna (None, None) se o endereço não puder ser geocodificado (quando `strict=False`).
    """
    parts = [p for p in (street, number, neighborhood, city, state, cep, 'Brasil') if p]
    query = ', '.join(parts)

    if (not city and not cep) or not settings.GEOCODING_URL:
        if strict:
            raise GeocodingError('Endereço incompleto ou serviço de geocodificação indisponível.')
        return None, None

    timeout = settings.GEOCODING_TIMEOUT_SECONDS
    max_attempts = max(1, getattr(settings, 'GEOCODING_MAX_ATTEMPTS', 2))
    client = get_http_client('geocoding', timeout=timeout)

    @with_network_retry(max_attempts=max_attempts)
    def _request() -> list[_NominatimResult]:
        response = client.get(
            settings.GEOCODING_URL,
            params={'q': query, 'format': 'json', 'limit': 2, 'countrycodes': 'br'},
            timeout=build_timeout(timeout),
        )
        response.raise_for_status()
        return _NOMINATIM_LIST_ADAPTER.validate_python(response.json())

    try:
        results = _request()
    except NETWORK_RETRY_EXCEPTIONS as exc:
        logger.warning('geocoding_failed reason=%s', type(exc).__name__)
        if strict:
            raise GeocodingError('Serviço de geocodificação indisponível no momento.') from None
        return None, None
    except (httpx.HTTPError, ValidationError, ValueError, TypeError) as exc:
        logger.warning('geocoding_failed reason=%s', type(exc).__name__)
        if strict:
            raise GeocodingError('Não foi possível confirmar o endereço.') from None
        return None, None

    if not results:
        if strict:
            raise GeocodingError('Endereço não encontrado.')
        return None, None

    if len(results) != 1 and not (street and number and city and cep):
        if strict:
            raise GeocodingError('Endereço ambíguo. Informe rua, número, cidade e CEP.')
        return None, None

    return float(results[0].lat), float(results[0].lon)
