"""Desenvolvimento local: defaults simples, com configuração opcional no .env."""

import os
from ipaddress import IPv4Address
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import dotenv_values

# Um caminho alternativo permite isolar ferramentas que não podem ler o .env habitual.
_env_file = Path(os.environ.get('NEXTROUTER_ENV_FILE') or Path(__file__).resolve().parents[2] / '.env')
for _name, _value in dotenv_values(_env_file).items():
    # O perfil é escolhido pelo comando, nunca pelo conteúdo do arquivo.
    if _name not in {'DJANGO_SETTINGS_MODULE', 'NEXTROUTER_ENV_FILE', 'NEXTROUTER_LAN_HOST'} and _value:
        os.environ[_name] = _value

from . import base as common  # ruff: ignore[module-import-not-at-top-of-file]
from .base import *  # ruff: ignore[module-import-not-at-top-of-file, undefined-local-with-import-star]

DEBUG = True
SECRET_KEY = os.getenv('SECRET_KEY') or 'chave-apenas-para-desenvolvimento-local'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']
_hosts = ['localhost', '127.0.0.1', '[::1]']
_lan_host = os.getenv('NEXTROUTER_LAN_HOST', '').strip()
if _lan_host:
    try:
        _address = IPv4Address(_lan_host)
    except ValueError:
        raise ImproperlyConfigured('Informe o IPv4 da máquina na rede confiável.') from None
    if _address.is_unspecified or _address.is_loopback or _address.is_multicast:
        raise ImproperlyConfigured('Informe o IPv4 da rede, não 0.0.0.0, loopback ou multicast.')
    _hosts.append(str(_address))
    ALLOWED_HOSTS.append(str(_address))

_origins = [f'http://{host}:{port}' for host in _hosts for port in (5173, 8000)]
FRONTEND_URL = (os.getenv('FRONTEND_URL') or 'http://127.0.0.1:5173').rstrip('/')
# Permite portas efêmeras nos harnesses, mas nunca origens arbitrárias/coringas.
try:
    _origin = urlsplit(FRONTEND_URL)
    _port = _origin.port
except ValueError:
    raise ImproperlyConfigured('FRONTEND_URL deve ser uma origem HTTP local válida.') from None
if (
    _origin.scheme != 'http'
    or _origin.hostname not in [host.strip('[]') for host in _hosts]
    or _origin.username is not None
    or _origin.password is not None
    or _origin.path
    or _origin.query
    or _origin.fragment
    or _port == 0
    or any(char in FRONTEND_URL for char in ('*', '\\', '?', '#'))
):
    raise ImproperlyConfigured('FRONTEND_URL deve usar um host local/LAN explicitamente autorizado, sem caminho.')
CORS_ALLOWED_ORIGINS = list(dict.fromkeys([*_origins, FRONTEND_URL]))
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
WS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS

# Sem URL explícita, banco dedicado em arquivo e canais/cache locais.
_supabase_database_url = os.getenv('SUPABASE_DATABASE_URL', '').strip()
_database_url = _supabase_database_url or os.getenv('DATABASE_URL', '').strip()
DATABASES = {
    'default': (
        common.parse_database_url(_database_url, is_supabase=bool(_supabase_database_url))
        if _database_url
        else {'ENGINE': 'django.db.backends.sqlite3', 'NAME': common.BASE_DIR / 'dev.sqlite3'}
    )
}
REDIS_URL = os.getenv('REDIS_URL', '').strip()
if REDIS_URL:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}}
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer', 'CONFIG': {'hosts': [REDIS_URL]}}}
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

# Imagens locais e documentos privados separados, inclusive nos dispositivos da rede.
MEDIA_ROOT = os.getenv('MEDIA_ROOT') or str(common.BASE_DIR / 'dev-media')
PRIVATE_DOCUMENT_ROOT = os.getenv('PRIVATE_DOCUMENT_ROOT') or str(common.BASE_DIR / 'dev-private-documents')
if not Path(PRIVATE_DOCUMENT_ROOT).is_absolute() or any(
    Path(PRIVATE_DOCUMENT_ROOT).resolve().is_relative_to(Path(root).resolve())
    for root in (MEDIA_ROOT, common.STATIC_ROOT, common.FRONTEND_DIST, *common.STATICFILES_DIRS)
):
    raise ImproperlyConfigured('PRIVATE_DOCUMENT_ROOT deve ser absoluto e ficar fora dos diretórios públicos.')
MEDIA_URL = '/media/'
STORAGES = {
    'default': {'BACKEND': common.MEDIA_STORAGE_BACKEND},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
EMAIL_BACKEND = (
    'django.core.mail.backends.smtp.EmailBackend'
    if common.EMAIL_HOST
    else 'django.core.mail.backends.console.EmailBackend'
)
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL') or common.EMAIL_HOST_USER or 'noreply@example.invalid'
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
