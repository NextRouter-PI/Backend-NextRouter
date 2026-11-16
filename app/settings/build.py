"""Somente collectstatic offline. Nunca usar este módulo para iniciar API ou worker."""

from .base import *  # ruff: ignore[undefined-local-with-import-star]

DEBUG = False
SECRET_KEY = 'chave-ficticia-apenas-para-coleta-offline-sem-runtime'
ALLOWED_HOSTS = []
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
