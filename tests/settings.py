"""Testes locais isolados: sem .env, banco habitual, Redis, SMTP ou Cloudinary."""

from pathlib import Path
from tempfile import TemporaryDirectory

from app.settings.base import *  # ruff: ignore[undefined-local-with-import-star]

DEBUG = False
SECRET_KEY = 'chave-ficticia-exclusiva-da-suite-local'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1', '[::1]']
FRONTEND_URL = 'http://127.0.0.1:5173'
CORS_ALLOWED_ORIGINS = ['http://localhost:5173', FRONTEND_URL, 'http://testserver']
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
WS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
REDIS_URL = CLOUDINARY_URL = OSRM_URL = GEOCODING_URL = ''
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
EMAIL_HOST = EMAIL_HOST_USER = EMAIL_HOST_PASSWORD = ''
DEFAULT_FROM_EMAIL = 'noreply@example.invalid'
EMAIL_TOKEN_EXPIRATION_MINUTES = 15
EMAIL_TOKEN_MAX_ATTEMPTS = 5
EMAIL_TOKEN_RESEND_SECONDS = 60
LOCATION_MAX_AGE_SECONDS = 30
LOCATION_MIN_INTERVAL_SECONDS = 2
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# A referência mantém os arquivos vivos durante o processo e os remove ao encerrar.
_files = TemporaryDirectory(prefix='nextrouter-tests-')
MEDIA_ROOT = str(Path(_files.name) / 'media')
PRIVATE_DOCUMENT_ROOT = str(Path(_files.name) / 'private')
FRONTEND_DIST = Path(_files.name) / 'frontend_dist'
MEDIA_URL = '/media/'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
