import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from . import base as common
from .base import *  # ruff: ignore[undefined-local-with-import-star]


def _required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ImproperlyConfigured(f'{name} é obrigatório em produção.')
    return value


DEBUG = False
SECRET_KEY = _required('SECRET_KEY')
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('SECRET_KEY deve ter pelo menos 50 caracteres e não ser chave de desenvolvimento.')

ALLOWED_HOSTS = [host.strip() for host in _required('ALLOWED_HOSTS').split(',') if host.strip()]
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS or any('://' in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('ALLOWED_HOSTS deve conter apenas nomes de host, sem curingas ou protocolo.')

CORS_ALLOWED_ORIGINS = [
    origin.strip().rstrip('/') for origin in _required('CORS_ALLOWED_ORIGINS').split(',') if origin.strip()
]
if not CORS_ALLOWED_ORIGINS or not all(origin.startswith('https://') for origin in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured('CORS_ALLOWED_ORIGINS deve conter apenas origens HTTPS.')
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

DATABASES = {'default': dj_database_url.parse(_required('DATABASE_URL'), conn_max_age=600, conn_health_checks=True)}
if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('DATABASE_URL deve apontar para PostgreSQL em produção.')
if not all(DATABASES['default'].get(key) for key in ('NAME', 'USER', 'PASSWORD', 'HOST')):
    raise ImproperlyConfigured('DATABASE_URL deve conter nome, usuário, senha e host do PostgreSQL.')

REDIS_URL = _required('REDIS_URL')
PRIVATE_DOCUMENT_ROOT = _required('PRIVATE_DOCUMENT_ROOT')
if Path(PRIVATE_DOCUMENT_ROOT).resolve().is_relative_to(Path(common.MEDIA_ROOT).resolve()):
    raise ImproperlyConfigured('PRIVATE_DOCUMENT_ROOT deve ficar fora de MEDIA_ROOT.')
OSRM_URL = _required('OSRM_URL')
GEOCODING_URL = _required('GEOCODING_URL')
if 'project-osrm.org' in OSRM_URL or 'nominatim.openstreetmap.org' in GEOCODING_URL:
    raise ImproperlyConfigured('Não use servidores públicos de demonstração para rotas de alunos.')

EMAIL_HOST = _required('EMAIL_HOST')
EMAIL_HOST_USER = _required('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = _required('EMAIL_HOST_PASSWORD')
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

MEDIA_URL = '/media/'
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
