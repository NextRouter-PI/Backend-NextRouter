from django.conf import settings
from django.utils import timezone
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication

from modules.accounts.models.user_session import UserSession


def dummy_get_response(request):
    return None


def enforce_csrf(request):
    check = CSRFCheck(dummy_get_response)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f'CSRF Failed: {reason}')


class CustomAuthentication(JWTAuthentication):
    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token'))
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        jti = str(validated_token.get('jti', ''))
        user = self.get_user(validated_token)
        session_is_active = UserSession.objects.filter(
            user=user, access_jti=jti, is_active=True, expires_at__gt=timezone.now()
        ).exists()
        if not session_is_active:
            raise exceptions.AuthenticationFailed()
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
