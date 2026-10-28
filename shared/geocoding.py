import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GeocodingError(ValueError):
    pass


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
