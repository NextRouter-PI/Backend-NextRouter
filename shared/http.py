"""Cliente HTTP compartilhado com connection pooling e retry exponencial com jitter."""

from threading import Lock

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

DEFAULT_HEADERS = {'User-Agent': 'NextRouter/1.0 (contato@nextrouter.com)'}
DEFAULT_LIMITS = httpx.Limits(max_keepalive_connections=10, max_connections=30, keepalive_expiry=30.0)
NETWORK_RETRY_EXCEPTIONS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)

_clients_lock = Lock()
_clients: dict[str, httpx.Client] = {}


def build_timeout(timeout: float) -> httpx.Timeout:
    """Constrói `httpx.Timeout` granular por fase (connect/read/write/pool)."""
    return httpx.Timeout(timeout, connect=min(timeout, 3.0), pool=2.0)


def get_http_client(name: str, *, timeout: float = 5.0) -> httpx.Client:
    """Retorna um `httpx.Client` nomeado com pool de conexões reutilizável."""
    with _clients_lock:
        client = _clients.get(name)
        if client is None or client.is_closed:
            client = httpx.Client(
                limits=DEFAULT_LIMITS,
                headers=DEFAULT_HEADERS,
                timeout=build_timeout(timeout),
            )
            _clients[name] = client
        return client


def with_network_retry(*, max_attempts: int = 2):
    """Decorator de retry para falhas transitórias de rede com backoff exponencial e jitter."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(max(1, max_attempts)),
        wait=wait_exponential_jitter(initial=0.1, max=2.0, jitter=0.1),
        retry=retry_if_exception_type(NETWORK_RETRY_EXCEPTIONS),
    )
