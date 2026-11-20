import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BRASILAPI_CEP_V2_URL = 'https://brasilapi.com.br/api/cep/v2/{cep}'


class GeocodingError(ValueError):
    pass


def lookup_cep_brasilapi(cep, *, timeout=None):
    """Consulta endereço e coordenadas aproximadas pela BrasilAPI CEP v2.

    Retorna dict {cep, state, city, neighborhood, street, latitude, longitude}
    ou None se não encontrado/indisponível. Nunca levanta exceção de rede.
    """
    clean_cep = ''.join(ch for ch in str(cep or '') if ch.isdigit())
    if len(clean_cep) != 8:
        return None

    req_timeout = timeout or getattr(settings, 'GEOCODING_TIMEOUT_SECONDS', 5)
    try:
        response = requests.get(
            BRASILAPI_CEP_V2_URL.format(cep=clean_cep),
            headers={'User-Agent': 'NextRouter/1.0 (contato@nextrouter.com)'},
            timeout=req_timeout,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning('brasilapi_cep_failed reason=%s', type(exc).__name__)
        return None

    coords = (payload.get('location') or {}).get('coordinates') or {}
    lat_raw = coords.get('latitude')
    lng_raw = coords.get('longitude')
    latitude = None
    longitude = None
    try:
        if lat_raw not in (None, '') and lng_raw not in (None, ''):
            lat_val = float(lat_raw)
            lng_val = float(lng_raw)
            if -90 <= lat_val <= 90 and -180 <= lng_val <= 180:
                latitude = lat_val
                longitude = lng_val
    except (TypeError, ValueError):
        latitude = None
        longitude = None

    return {
        'cep': clean_cep,
        'state': str(payload.get('state') or '').strip().upper()[:2],
        'city': str(payload.get('city') or '').strip(),
        'neighborhood': str(payload.get('neighborhood') or '').strip(),
        'street': str(payload.get('street') or '').strip(),
        'latitude': latitude,
        'longitude': longitude,
    }


def geocode_address(*, street='', number='', neighborhood='', city='', state='', cep='', strict=False):
    """
    Converte um endereço em coordenadas (latitude, longitude) usando a API pública
    do Nominatim/OpenStreetMap (sem necessidade de chave de API).

    Retorna (None, None) se o endereço não puder ser geocodificado — nunca levanta
    exceção, para que uma falha de rede não impeça a criação/edição de um cadastro.
    """
    parts = [p for p in (street, number, neighborhood, city, state, cep, 'Brasil') if p]
    query = ', '.join(parts)

    if (not city and not cep) or not settings.GEOCODING_URL:
        # Endereço incompleto demais para gerar uma geocodificação confiável.
        if strict:
            raise GeocodingError('Endereço incompleto ou serviço de geocodificação indisponível.')
        return None, None

    max_attempts = max(1, getattr(settings, 'GEOCODING_MAX_ATTEMPTS', 2))
    results = None
    for attempt in range(max_attempts):
        try:
            response = requests.get(
                settings.GEOCODING_URL,
                params={'q': query, 'format': 'json', 'limit': 2, 'countrycodes': 'br'},
                headers={'User-Agent': 'NextRouter/1.0 (contato@nextrouter.com)'},
                timeout=settings.GEOCODING_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            results = response.json()
            break
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == max_attempts - 1:
                logger.warning('geocoding_failed reason=%s', type(exc).__name__)
                if strict:
                    raise GeocodingError('Serviço de geocodificação indisponível no momento.') from None
                return None, None
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            logger.warning('geocoding_failed reason=%s', type(exc).__name__)
            if strict:
                raise GeocodingError('Não foi possível confirmar o endereço.') from None
            return None, None

    try:
        if not results:
            if strict:
                raise GeocodingError('Endereço não encontrado.')
            return None, None

        if len(results) != 1 and not (street and number and city and cep):
            raise GeocodingError('Endereço ambíguo. Informe rua, número, cidade e CEP.')

        return float(results[0]['lat']), float(results[0]['lon'])
    except GeocodingError:
        if strict:
            raise
        return None, None
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning('geocoding_failed reason=%s', type(exc).__name__)
        if strict:
            raise GeocodingError('Não foi possível confirmar o endereço.') from None
        return None, None
