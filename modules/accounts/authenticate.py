from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password

from modules.accounts.models.user_session import UserSession


def dummy_get_response(request):
    return None


def enforce_csrf(request):
    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f'CSRF Failed: {reason}')


def authenticate_session_from_token(validated_token):
    """Valida usuário ativo, `CHECK_REVOKE_TOKEN` e `UserSession` ativa em uma única query."""
    jti = str(validated_token.get('jti', ''))
    user_id = validated_token.get(api_settings.USER_ID_CLAIM)
    if not jti or not user_id:
        raise exceptions.AuthenticationFailed()
    session = UserSession.objects.for_access_jti(jti, user_id=user_id).with_user().first()
    if session is None:
        raise exceptions.AuthenticationFailed()
    user = session.user
    if api_settings.CHECK_REVOKE_TOKEN and validated_token.get(
        api_settings.REVOKE_TOKEN_CLAIM
    ) != get_md5_hash_password(user.password):
        raise exceptions.AuthenticationFailed()
    return user, jti


class CustomAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'))
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        user, _ = authenticate_session_from_token(validated_token)
        if request.method not in (
            'GET',
            'HEAD',
            'OPTIONS',
        ):
            enforce_csrf(request)
        return user, validated_token

    def authenticate_header(self, request):
        return 'Cookie'


class CustomAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'modules.accounts.authenticate.CustomAuthentication'
    name = 'cookieAuth'

    def get_security_definition(self, auto_schema):
        return {'type': 'apiKey', 'in': 'cookie', 'name': 'access_token'}
