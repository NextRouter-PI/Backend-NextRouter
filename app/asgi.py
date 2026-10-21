"""
ASGI config for app project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

import django

django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter  # ruff: ignore[module-import-not-at-top-of-file]
from django.core.asgi import get_asgi_application  # ruff: ignore[module-import-not-at-top-of-file]

from app.jwt_ws_auth import JWTAuthMiddleware  # ruff: ignore[module-import-not-at-top-of-file]
from router.routing import websocket_urlpatterns  # ruff: ignore[module-import-not-at-top-of-file]

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
})
