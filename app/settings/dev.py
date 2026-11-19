"""Desenvolvimento local sem serviços obrigatórios ou leitura automática de .env."""

import os
from ipaddress import IPv4Address
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from . import base as common
from .base import *  # ruff: ignore[undefined-local-with-import-star]

DEBUG = True
SECRET_KEY = os.getenv('DEV_SECRET_KEY') or 'chave-apenas-para-desenvolvimento-local'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']
_hosts = ['localhost', '127.0.0.1', '[::1]']
_lan_host = os.getenv('DEV_LAN_HOST', '').strip()
if _lan_host:
    try:
        _address = IPv4Address(_lan_host)
    except ValueError:
        raise ImproperlyConfigured('DEV_LAN_HOST deve ser o IPv4 da máquina na rede confiável.') from None
    if _address.is_unspecified or _address.is_loopback or _address.is_multicast:
        raise ImproperlyConfigured('Informe o IPv4 da rede, não 0.0.0.0, loopback ou multicast.')
    _hosts.append(str(_address))
    ALLOWED_HOSTS.append(str(_address))

_origins = [f'http://{host}:{port}' for host in _hosts for port in (5173, 8000)]
FRONTEND_URL = os.getenv('DEV_FRONTEND_ORIGIN', 'http://127.0.0.1:5173').rstrip('/')
# Permite portas efêmeras nos harnesses, mas nunca origens arbitrárias/coringas.
try:
    _origin = urlsplit(FRONTEND_URL)
    _port = _origin.port
except ValueError:
    raise ImproperlyConfigured('DEV_FRONTEND_ORIGIN deve ser uma origem HTTP local válida.') from None
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
    raise ImproperlyConfigured('DEV_FRONTEND_ORIGIN deve usar um host local/LAN explicitamente autorizado, sem caminho.')
CORS_ALLOWED_ORIGINS = list(dict.fromkeys([*_origins, FRONTEND_URL]))
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
WS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS

# Não reutilizar DATABASE_URL/REDIS_URL nem o db.sqlite3 habitual.
_database = Path(os.getenv('DEV_DATABASE_PATH') or common.BASE_DIR / 'dev.sqlite3').expanduser()
if not _database.is_absolute():
    _database = common.BASE_DIR / _database
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': _database}}
REDIS_URL = ''
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

# Imagens locais e documentos privados separados, inclusive nos dispositivos da rede.
MEDIA_ROOT = os.getenv('DEV_MEDIA_ROOT') or str(common.BASE_DIR / 'dev-media')
PRIVATE_DOCUMENT_ROOT = os.getenv('DEV_PRIVATE_DOCUMENT_ROOT') or str(common.BASE_DIR / 'dev-private-documents')
if not Path(PRIVATE_DOCUMENT_ROOT).is_absolute() or any(
    Path(PRIVATE_DOCUMENT_ROOT).resolve().is_relative_to(Path(root).resolve())
    for root in (MEDIA_ROOT, common.STATIC_ROOT, common.FRONTEND_DIST, *common.STATICFILES_DIRS)
):
    raise ImproperlyConfigured('DEV_PRIVATE_DOCUMENT_ROOT deve ser absoluto e ficar fora dos diretórios públicos.')
MEDIA_URL = '/media/'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@example.invalid'
GEOCODING_URL = os.getenv('DEV_GEOCODING_URL', '')
OSRM_URL = os.getenv('DEV_OSRM_URL', '')
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
