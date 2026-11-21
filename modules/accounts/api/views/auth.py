from django.db import transaction
from django.middleware.csrf import get_token, rotate_token
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from modules.accounts.api.serializers.session import CustomTokenObtainPairSerializer, UserSessionSerializer
from modules.accounts.authenticate import enforce_csrf
from modules.accounts.http import clear_auth_cookies, get_request_ip, set_auth_cookies
from modules.accounts.models import UserSession
from modules.accounts.services import (
    create_user_session,
    deactivate_account,
    logout_user_session,
    refresh_user_session,
    revoke_session,
    revoke_sessions,
)
from shared.exceptions import DomainError
from shared.openapi import RESP_400_VALIDATION, RESP_401_UNAUTHORIZED, RESP_403_FORBIDDEN, RESP_429_THROTTLED

DETAIL_RESPONSE = inline_serializer('AuthDetailResponse', fields={'detail': serializers.CharField()})


class CsrfView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=['Autenticação'],
        summary='Obtenha o token CSRF',
        description='Público. Fornece CSRF para operações com cookies; não é JWT nem autentica usuário.',
        responses=inline_serializer('CsrfToken', fields={'csrfToken': serializers.CharField()}),
    )
    def get(self, request):
        return Response({'csrfToken': get_token(request)})


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'login'
    authentication_classes = ()

    @extend_schema(
        tags=['Autenticação'],
        summary='Acesse a conta',
        description=(
            'Público, com CSRF. Verifica e-mail/senha e cria sessão em cookies HttpOnly; nunca retorna JWT. '
            'Login limitado por taxa.'
        ),
        request=TokenObtainPairSerializer,
        responses={
            200: inline_serializer(
                'AuthSessionResponse',
                fields={
                    'detail': serializers.CharField(),
                    'csrfToken': serializers.CharField(),
                },
            ),
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
            429: RESP_429_THROTTLED,
        },
        examples=[
            OpenApiExample(
                'Login fictício',
                value={
                    'email': 'aluno@exemplo.com.br',
                    'password': 'SenhaFicticia!123',
                },
                request_only=True,
            ),
            OpenApiExample(
                'Sessão criada',
                value={'detail': 'Sessão iniciada.', 'csrfToken': '<csrf-mascarado>'},
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        enforce_csrf(request)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data
        create_user_session(
            serializer.user,
            tokens,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            ip_address=get_request_ip(request),
        )
        rotate_token(request)
        response = Response({'detail': 'Sessão iniciada.', 'csrfToken': get_token(request)})
        return set_auth_cookies(response, tokens)


class CustomTokenRefreshView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get_authenticate_header(self, request):
        return 'Cookie'

    @extend_schema(
        tags=['Autenticação'],
        summary='Renove a sessão',
        description=(
            'Público, com cookie refresh_token e CSRF válidos. Rotaciona refresh, atualiza sessão e cookies; '
            'não envie token no corpo.'
        ),
        request=None,
        responses={
            200: DETAIL_RESPONSE,
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
        },
    )
    def post(self, request):
        enforce_csrf(request)
        if request.data:
            raise ValidationError('A renovação usa somente cookie, sem corpo de requisição.')
        tokens = refresh_user_session(request.COOKIES.get('refresh_token'))
        return set_auth_cookies(Response({'detail': 'Sessão renovada.'}), tokens)


class CustomLogoutView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=['Autenticação'],
        summary='Saia da conta',
        description='Aceita sessão ativa ou já inválida; exige CSRF. Revoga tokens e limpa cookies.',
        request=None,
        responses={200: DETAIL_RESPONSE},
    )
    def post(self, request):
        enforce_csrf(request)
        logout_user_session(
            raw_access_token=request.COOKIES.get('access_token'),
            raw_refresh_token=request.COOKIES.get('refresh_token'),
        )
        return clear_auth_cookies(Response({'detail': 'Logout efetuado com sucesso.'}))


class UserSessionsView(APIView):
    @extend_schema(
        tags=['Autenticação'],
        summary='Liste suas sessões',
        description='Apenas usuário autenticado; retorna dispositivos e indica a sessão atual.',
        responses={200: UserSessionSerializer(many=True)},
    )
    def get(self, request):
        sessions = request.user.sessions.active()
        serializer = UserSessionSerializer(sessions, many=True, context={'current_jti': request.auth['jti']})
        return Response(serializer.data)


class UserSessionDeactivateView(APIView):
    @extend_schema(
        tags=['Autenticação'],
        summary='Revogue outra sessão',
        description='Apenas titular autenticado. Não permite revogar a sessão atual por este endpoint; use logout.',
        request=None,
        responses={200: DETAIL_RESPONSE},
    )
    def delete(self, request, session_id):
        session = get_object_or_404(UserSession, pk=session_id, user=request.user)
        if session.access_jti == request.auth['jti']:
            raise ValidationError('Use logout para encerrar a sessão atual.')
        revoke_session(session)
        return Response({'detail': 'Sessão revogada.'})


class RevokeAllSessionsView(APIView):
    @extend_schema(
        tags=['Autenticação'],
        summary='Revogue todas as sessões',
        description='Apenas titular autenticado. Revoga todos os dispositivos e limpa cookies.',
        request=None,
        responses={200: DETAIL_RESPONSE},
    )
    def post(self, request):
        revoke_sessions(request.user)
        return clear_auth_cookies(Response({'detail': 'Todas as sessões foram revogadas.'}))


class DeactivateSelfView(APIView):
    @extend_schema(
        tags=['Autenticação'],
        summary='Desative sua conta',
        description=(
            'Apenas titular autenticado. Desativa conta e revoga sessões; '
            'último administrador ativo não pode se desativar.'
        ),
        request=None,
        responses={200: DETAIL_RESPONSE},
    )
    def post(self, request):
        try:
            deactivate_account(actor_id=request.user.pk, user_id=request.user.pk)
        except DomainError as exc:
            raise ValidationError(exc.messages) from exc
        return clear_auth_cookies(Response({'detail': 'Conta desativada.'}))
