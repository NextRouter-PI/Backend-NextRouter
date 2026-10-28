"""
ASGI config for app project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings.prod')

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # ruff: ignore[module-import-not-at-top-of-file]
from channels.security.websocket import OriginValidator  # ruff: ignore[module-import-not-at-top-of-file]
from django.conf import settings  # ruff: ignore[module-import-not-at-top-of-file]

from modules.accounts.ws_auth import JWTAuthMiddleware  # ruff: ignore[module-import-not-at-top-of-file]
from modules.transport.routing import websocket_urlpatterns  # ruff: ignore[module-import-not-at-top-of-file]

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': OriginValidator(JWTAuthMiddleware(URLRouter(websocket_urlpatterns)), settings.CORS_ALLOWED_ORIGINS),
})
