# core/auth_views.py

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            refresh_token = response.data.get('refresh')

            del response.data['refresh']

            response.set_cookie(
                key='refresh_token',
                value=refresh_token,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=24 * 60 * 60,
            )

        return response


class CustomTokenRefreshView(APIView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response({'detail': 'Refresh token ausente.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = TokenRefreshSerializer(data={'refresh': refresh_token})

        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            response = Response({'detail': 'Token inválido ou expirado.'}, status=status.HTTP_401_UNAUTHORIZED)
            response.delete_cookie('refresh_token')
            return response

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)

        if 'refresh' in serializer.validated_data:
            new_refresh = serializer.validated_data['refresh']
            del response.data['refresh']
            response.set_cookie(
                key='refresh_token',
                value=new_refresh,
                httponly=True,
                secure=not settings.DEBUG,
                samesite='Lax',
                max_age=24 * 60 * 60,
            )

        return response


class CustomLogoutView(APIView):
    def post(self, request):
        response = Response({'detail': 'Logout efetuado com sucesso.'}, status=status.HTTP_200_OK)
        response.delete_cookie('refresh_token', samesite='Lax')
        return response
