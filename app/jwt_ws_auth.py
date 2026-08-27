from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


@database_sync_to_async
def get_user_from_token(token):
    try:
        auth = JWTAuthentication()
        validated_token = auth.get_validated_token(token)
        return auth.get_user(validated_token)
    except (InvalidToken, TokenError):
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Autentica conexões WebSocket via JWT passado como query string:
    ws://host/ws/travels/<id>/location/?token=<access_token>

    Necessário porque o navegador não permite enviar cabeçalhos customizados
    (como Authorization) durante o handshake do WebSocket.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        scope['user'] = await get_user_from_token(token) if token else AnonymousUser()

        return await self.app(scope, receive, send)
