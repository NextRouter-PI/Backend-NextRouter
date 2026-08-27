import logging

import requests

logger = logging.getLogger(__name__)

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
REQUEST_TIMEOUT_SECONDS = 5


def geocode_address(*, street='', number='', neighborhood='', city='', state='', cep=''):
    """
    Converte um endereço em coordenadas (latitude, longitude) usando a API pública
    do Nominatim/OpenStreetMap (sem necessidade de chave de API).

    Retorna (None, None) se o endereço não puder ser geocodificado — nunca levanta
    exceção, para que uma falha de rede não impeça a criação/edição de um cadastro.
    """
    parts = [p for p in (street, number, neighborhood, city, state, cep, 'Brasil') if p]
    query = ', '.join(parts)

    if not city and not cep:
        # Endereço incompleto demais para gerar uma geocodificação confiável.
        return None, None

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={'q': query, 'format': 'json', 'limit': 1, 'countrycodes': 'br'},
            headers={'User-Agent': 'NextRouter/1.0 (contato@nextrouter.com)'},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        results = response.json()

        if not results:
            return None, None

        return float(results[0]['lat']), float(results[0]['lon'])
    except Exception:
        logger.warning('Não foi possível geocodificar o endereço: %s', query, exc_info=True)
        return None, None
