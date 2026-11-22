import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from . import base as common
from .base import *  # ruff: ignore[undefined-local-with-import-star]


def _required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ImproperlyConfigured(f'{name} é obrigatório em produção.')
    return value


def _boolean(name, default='false'):
    value = os.environ.get(name, default).strip().lower()
    if value not in ('true', 'false'):
        raise ImproperlyConfigured(f'{name} deve ser true ou false.')
    return value == 'true'


def _nonnegative_integer(name, default='0'):
    value = os.environ.get(name, default).strip()
    if not value.isascii() or not value.isdecimal() or int(value) > 2147483647:
        raise ImproperlyConfigured(f'{name} deve ser um inteiro não negativo válido.')
    return int(value)


def _routing_url(name, *, required=False):
    value = _required(name) if required else os.environ.get(name, '').strip()
    if not value:
        return ''
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ImproperlyConfigured(f'{name} deve ser uma URL HTTP(S) válida.') from None
    if (
        parsed.scheme not in ('http', 'https')
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or port == 0
        or any(
            parsed.hostname.lower().rstrip('.') == demo or parsed.hostname.lower().rstrip('.').endswith('.' + demo)
            for demo in ('project-osrm.org', 'nominatim.openstreetmap.org')
        )
    ):
        raise ImproperlyConfigured(
            f'{name} deve usar serviço autorizado, sem credenciais/query ou servidores demo públicos.'
        )
    return value


DEBUG = False
SECRET_KEY = _required('SECRET_KEY')
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('SECRET_KEY deve ter pelo menos 50 caracteres e não ser chave de desenvolvimento.')

ALLOWED_HOSTS = [host.strip() for host in _required('ALLOWED_HOSTS').split(',') if host.strip()]
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS or any('://' in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('ALLOWED_HOSTS deve conter apenas nomes de host, sem curingas ou protocolo.')

PUBLIC_ORIGIN = _required('PUBLIC_ORIGIN')
try:
    _origin = urlsplit(PUBLIC_ORIGIN)
    _port = _origin.port
except ValueError as exc:
    raise ImproperlyConfigured('PUBLIC_ORIGIN deve ser uma origem HTTPS válida.') from exc
if (
    _origin.scheme != 'https'
    or not _origin.hostname
    or _origin.hostname not in ALLOWED_HOSTS
    or _origin.username is not None
    or _origin.password is not None
    or _origin.path
    or _origin.query
    or _origin.fragment
    or '*' in PUBLIC_ORIGIN
    or any(value in PUBLIC_ORIGIN for value in ('?', '#', '\\'))
    or _port == 0
):
    raise ImproperlyConfigured('PUBLIC_ORIGIN deve ser uma origem HTTPS sem caminho, de um host autorizado.')
CORS_ALLOWED_ORIGINS = []
CSRF_TRUSTED_ORIGINS = [PUBLIC_ORIGIN]
WS_ALLOWED_ORIGINS = [PUBLIC_ORIGIN]
FRONTEND_URL = FRONTEND_ADMIN_URL = PUBLIC_ORIGIN
BACKEND_REVISION = os.environ.get('BACKEND_REVISION', '')

# ASGI usa pool psycopg3 com conn_max_age=0 (ou Supavisor/PgBouncer externo no Supabase).
_supabase_database_url = os.environ.get('SUPABASE_DATABASE_URL', '').strip()
_database_url = _supabase_database_url or _required('DATABASE_URL')
_database = common.parse_database_url(
    _database_url,
    is_supabase=bool(_supabase_database_url),
    enable_pool=True,
)
DATABASES = {'default': _database}
if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('DATABASE_URL deve apontar para PostgreSQL em produção.')
if not all(DATABASES['default'].get(key) for key in ('NAME', 'USER', 'PASSWORD', 'HOST')):
    raise ImproperlyConfigured('DATABASE_URL deve conter nome, usuário, senha e host do PostgreSQL.')

REDIS_URL = os.environ.get('REDIS_URL', '').strip()
if REDIS_URL:
    try:
        _redis = urlsplit(REDIS_URL)
        _redis_port = _redis.port
    except ValueError:
        raise ImproperlyConfigured('REDIS_URL deve apontar para Redis/Redis TLS válido.') from None
    if _redis.scheme not in ('redis', 'rediss') or not _redis.hostname or _redis_port == 0:
        raise ImproperlyConfigured('REDIS_URL deve apontar para Redis/Redis TLS.')
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}}
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer', 'CONFIG': {'hosts': [REDIS_URL]}}}
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

PRIVATE_DOCUMENT_ROOT = os.environ.get('PRIVATE_DOCUMENT_ROOT', '').strip() or str(
    common.BASE_DIR / 'private-documents'
)
if not Path(PRIVATE_DOCUMENT_ROOT).is_absolute() or any(
    Path(PRIVATE_DOCUMENT_ROOT).resolve().is_relative_to(Path(root).resolve())
    for root in (common.MEDIA_ROOT, common.STATIC_ROOT, common.FRONTEND_DIST, *common.STATICFILES_DIRS)
):
    raise ImproperlyConfigured('PRIVATE_DOCUMENT_ROOT deve ser absoluto e ficar fora de diretórios públicos.')
OSRM_URL = _routing_url('OSRM_URL')
GEOCODING_URL = _routing_url('GEOCODING_URL')

EMAIL_HOST = os.environ.get('EMAIL_HOST', '').strip()
if EMAIL_HOST:
    EMAIL_HOST_USER = _required('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = _required('EMAIL_HOST_PASSWORD')
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '').strip()
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '').strip()
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

MEDIA_URL = '/media/'
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
SECURE_HSTS_SECONDS = _nonnegative_integer('HSTS_SECONDS')
SECURE_HSTS_INCLUDE_SUBDOMAINS = _boolean('HSTS_INCLUDE_SUBDOMAINS')
SECURE_HSTS_PRELOAD = _boolean('HSTS_PRELOAD')
if (SECURE_HSTS_INCLUDE_SUBDOMAINS or SECURE_HSTS_PRELOAD) and SECURE_HSTS_SECONDS == 0:
    raise ImproperlyConfigured('Habilite HSTS antes de incluir subdomínios/preload; confirme o controle do domínio.')
_default_trust_proxy = 'true' if os.environ.get('RENDER', '').strip().lower() == 'true' else 'false'
TRUST_PROXY_HEADERS = _boolean('TRUST_PROXY_HEADERS', default=_default_trust_proxy)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if TRUST_PROXY_HEADERS else None
# Exceção mínima sem dados para o probe HTTP interno; readiness continua exigindo HTTPS.
SECURE_REDIRECT_EXEMPT = [r'^health/live/$']
# Em django-ipware 8+, `proxy_count` conta proxies intermediários dentro do XFF (0 = 1 proxy reverso confiável).
IPWARE_PROXY_COUNT = 0
IPWARE_STRICT = not TRUST_PROXY_HEADERS
IPWARE_HEADER_ORDER = ['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'] if TRUST_PROXY_HEADERS else ['REMOTE_ADDR']
REST_FRAMEWORK = {**common.REST_FRAMEWORK, 'NUM_PROXIES': 1 if TRUST_PROXY_HEADERS else 0}
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'operational': {'()': 'app.operational_logging.OperationalFormatter'}},
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'operational'},
        'null': {'class': 'logging.NullHandler'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.server': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'daphne.access': {'handlers': ['null'], 'propagate': False},
    },
}
