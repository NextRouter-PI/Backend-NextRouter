from django.conf import settings
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
        is_cookie_auth = False
        header = self.get_header(request)
        if header is None:
            cookie_name = settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token')
            raw_token = request.COOKIES.get(cookie_name)
            if raw_token:
                is_cookie_auth = True
            else:
                raw_token = None
        else:
            raw_token = self.get_raw_token(header)

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        jti = str(validated_token.get('jti', ''))
        session_is_active = UserSession.objects.filter(access_jti=jti, is_active=True).exists()
        if not session_is_active:
            raise exceptions.AuthenticationFailed()
        if is_cookie_auth and request.method not in (
            'GET',
            'HEAD',
            'OPTIONS',
        ):
            enforce_csrf(request)
        return self.get_user(validated_token), validated_token


class CustomAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'modules.accounts.authenticate.CustomAuthentication'
    name = ('bearerAuth', 'cookieAuth')

    def get_security_definition(self, auto_schema):
        return [
            {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'},
            {'type': 'apiKey', 'in': 'cookie', 'name': 'access_token'},
        ]
