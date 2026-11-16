from http.cookies import CookieError, SimpleCookie

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from modules.accounts.authenticate import CustomAuthentication
from modules.accounts.models.user_session import UserSession


@database_sync_to_async
def get_user_from_token(token):
    try:
        auth = CustomAuthentication()
        validated_token = auth.get_validated_token(token)
        user = auth.get_user(validated_token)
        if UserSession.objects.filter(
            user=user, access_jti=validated_token['jti'], is_active=True, expires_at__gt=timezone.now()
        ).exists():
            return user, validated_token['jti'], validated_token['exp']
        return AnonymousUser(), None, None
    except (InvalidToken, TokenError, AuthenticationFailed):
        # Token inválido/expirado ou usuário inexistente/inativo.
        return AnonymousUser(), None, None


class JWTAuthMiddleware:
    """
    Usa o cookie HttpOnly, evitando colocar tokens em URLs e logs de proxy.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        cookies = SimpleCookie()
        for header, value in scope.get('headers', []):
            header_name = header.lower()
            if header_name == b'cookie':
                try:
                    cookies.load(value.decode('latin1'))
                except CookieError:
                    cookies = SimpleCookie()
        token_cookie = cookies.get('access_token')
        token = token_cookie.value if token_cookie else None

        scope['user'], scope['access_jti'], scope['access_exp'] = (
            await get_user_from_token(token) if token else (AnonymousUser(), None, None)
        )

        return await self.app(scope, receive, send)
