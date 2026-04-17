from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed, ParseError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User


class TokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'core.authentication.TokenAuthentication'
    name = 'tokenAuth'
    match_subclasses = True
    priority = -1

    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(
            header_name='Authorization',
            token_prefix='Bearer',
        )


class TokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request) -> tuple[User, None]:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        try:
            prefix, token = auth_header.split()
            if prefix.lower() != 'bearer':
                return None
        except ValueError:
            return None

        try:
            jwt_token = RefreshToken(token)
            user_id = jwt_token['user_id']
            user = User.objects.get(id=user_id)
            return (user, None)
        except (TokenError, ParseError, KeyError, ObjectDoesNotExist) as e:
            raise AuthenticationFailed(f'Token inválido: {str(e)}') from e

    def authenticate_header(self, request):
        return 'Bearer'


def generate_tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }
