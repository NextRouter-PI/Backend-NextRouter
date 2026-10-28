import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env')

from . import base as common  # ruff: ignore[module-import-not-at-top-of-file]
from .base import *  # ruff: ignore[undefined-local-with-import-star, module-import-not-at-top-of-file]

DEBUG = True
SECRET_KEY = os.getenv('SECRET_KEY') or 'chave-apenas-para-desenvolvimento-local'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']

_origins = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:3000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:8080',
    'http://127.0.0.1:8080',
    *[url.rstrip('/') for url in (common.FRONTEND_URL, common.FRONTEND_ADMIN_URL) if url],
]
CORS_ALLOWED_ORIGINS = list(dict.fromkeys(_origins))
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

DATABASES = {
    'default': dj_database_url.parse(
        os.getenv('DATABASE_URL') or f'sqlite:///{common.BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        conn_health_checks=True,
    )
}
BACKEND_HOST = os.getenv('BACKEND_HOST', '127.0.0.1')
BACKEND_PORT = os.getenv('BACKEND_PORT', '8000')
MEDIA_URL = f'http://{BACKEND_HOST}:{BACKEND_PORT}/media/'
STORAGES = {**common.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
EMAIL_BACKEND = (
    'django.core.mail.backends.smtp.EmailBackend'
    if common.EMAIL_HOST
    else 'django.core.mail.backends.console.EmailBackend'
)
