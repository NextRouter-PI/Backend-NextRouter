from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

REFRESH_COOKIE_NAME = 'refresh_token'

DETAIL_RESPONSE = inline_serializer('DetailResponse', fields={'detail': serializers.CharField()})


def _refresh_cookie_samesite():
    # Em produção o front-end (Vercel) e a API ficam em domínios diferentes: com SameSite=Lax o
    # navegador não envia o cookie nas requisições cross-site e o refresh nunca funcionaria.
    return 'Lax' if settings.DEBUG else 'None'


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite=_refresh_cookie_samesite(),
        max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
    )


def delete_refresh_cookie(response):
    response.delete_cookie(REFRESH_COOKIE_NAME, samesite=_refresh_cookie_samesite())


class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            set_refresh_cookie(response, response.data.pop('refresh'))

        return response


class CustomTokenRefreshView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        request=None,
        summary='Gera um novo token de acesso a partir do cookie refresh_token.',
        responses={
            200: inline_serializer('AccessTokenResponse', fields={'access': serializers.CharField()}),
            401: DETAIL_RESPONSE,
        },
    )
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE_NAME)

        if not refresh_token:
            return Response({'detail': 'Refresh token ausente.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = TokenRefreshSerializer(data={'refresh': refresh_token})

        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            response = Response({'detail': 'Token inválido ou expirado.'}, status=status.HTTP_401_UNAUTHORIZED)
            delete_refresh_cookie(response)
            return response

        data = dict(serializer.validated_data)
        new_refresh = data.pop('refresh', None)
        response = Response(data, status=status.HTTP_200_OK)

        if new_refresh:
            set_refresh_cookie(response, new_refresh)

        return response


class CustomLogoutView(APIView):
    # O logout precisa funcionar mesmo com o token de acesso já expirado.
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(request=None, summary='Remove o cookie refresh_token.', responses={200: DETAIL_RESPONSE})
    def post(self, request):
        response = Response({'detail': 'Logout efetuado com sucesso.'}, status=status.HTTP_200_OK)
        delete_refresh_cookie(response)
        return response
