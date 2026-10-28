from django.conf import settings
from django.db import transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from ipware import get_client_ip
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from user_agents import parse

from modules.accounts.authenticate import CustomAuthentication, enforce_csrf
from modules.accounts.models import User, UserSession
from modules.accounts.services import revoke_session, revoke_sessions
from shared.openapi import RESP_400_VALIDATION, RESP_401_UNAUTHORIZED, RESP_403_FORBIDDEN, RESP_429_THROTTLED


def get_request_ip(request):
    ip, _ = get_client_ip(
        request,
        proxy_count=getattr(settings, 'IPWARE_PROXY_COUNT', 0),
        proxy_trusted_ips=getattr(settings, 'IPWARE_TRUSTED_PROXIES', []),
        request_header_order=getattr(settings, 'IPWARE_HEADER_ORDER', ['X_FORWARDED_FOR', 'REMOTE_ADDR']),
    )
    return ip


DETAIL_RESPONSE = inline_serializer('AuthDetailResponse', fields={'detail': serializers.CharField()})
SESSION_RESPONSE = inline_serializer(
    'UserSessionResponse',
    fields={
        'id': serializers.UUIDField(),
        'device': serializers.CharField(),
        'ip': serializers.IPAddressField(allow_null=True),
        'created_at': serializers.DateTimeField(),
        'current': serializers.BooleanField(),
    },
    many=True,
)


def cookie_options():
    return {'httponly': True, 'secure': not settings.DEBUG, 'samesite': 'Lax' if settings.DEBUG else 'None'}


def set_auth_cookies(response, data):
    for name, lifetime in [('access', 'ACCESS_TOKEN_LIFETIME'), ('refresh', 'REFRESH_TOKEN_LIFETIME')]:
        response.set_cookie(
            f'{name}_token',
            data[name],
            max_age=int(settings.SIMPLE_JWT[lifetime].total_seconds()),
            **cookie_options(),
        )


def clear_auth_cookies(response):
    for name in ('access_token', 'refresh_token'):
        response.set_cookie(
            name,
            '',
            max_age=0,
            expires='Thu, 01 Jan 1970 00:00:00 GMT',
            path='/',
            **cookie_options(),
        )
    return response


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
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'login'
    authentication_classes = ()

    @extend_schema(
        tags=['Autenticação'],
        summary='Acesse a conta',
        description=(
            'Público, com CSRF. Verifica e-mail/senha e cria sessão; retorna JWT no corpo e cookies HttpOnly. '
            'Login limitado por taxa.'
        ),
        responses={
            200: inline_serializer(
                'AuthTokensResponse',
                fields={
                    'access': serializers.CharField(),
                    'refresh': serializers.CharField(),
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
                'Tokens fictícios (não utilizáveis)',
                value={'access': '<jwt-ficticio>', 'refresh': '<jwt-ficticio>'},
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        enforce_csrf(request)
        # 1. Faz uma cópia independente dos dados da requisição
        data = request.data.copy()

        # 2. Verifica se há e-mail
        if isinstance(data.get('email'), str):
            # 3. Renova a variável formatando o e-mail para letras maiúsculas e removendo espaços em branco
            data['email'] = data['email'].strip().lower()

            # 4. Verifica se o e-mail formatado existe no banco de dados
            stored_email = User.objects.filter(email__iexact=data['email']).values_list('email', flat=True).first()
            if stored_email:
                data['email'] = stored_email

        # 5. Serializa os dados enviados na requisição
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data

        # 6. Cria o registro do login na tabela de sessão
        ua = parse(request.META.get('HTTP_USER_AGENT', ''))

        UserSession.objects.create(
            user=serializer.user,
            access_jti=AccessToken(tokens['access'])['jti'],
            refresh_jti=RefreshToken(tokens['refresh'])['jti'],
            device_name=f'{ua.browser.family} em {ua.os.family}'[:255],
            device_type='mobile' if ua.is_mobile else 'tablet' if ua.is_tablet else 'desktop',
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
            ip_address=get_request_ip(request),
            expires_at=timezone.now() + settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
        )
        # TODO: remover tokens do corpo da requisição
        response = Response({
            'access': tokens['access'],
            'refresh': tokens['refresh'],
        })
        set_auth_cookies(response, tokens)
        get_token(request)
        return response


class CustomTokenRefreshView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get_authenticate_header(self, request):
        return 'Bearer'

    @extend_schema(
        tags=['Autenticação'],
        summary='Renove a sessão',
        description=(
            'Público, com cookie refresh_token e CSRF válidos. Rotaciona refresh, atualiza sessão e cookies; '
            'não envie token no corpo.'
        ),
        request=None,
        responses={
            200: inline_serializer('AccessTokenResponse', fields={'access': serializers.CharField()}),
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
        },
    )
    @transaction.atomic
    def post(self, request):
        enforce_csrf(request)
        raw = request.COOKIES.get('refresh_token')
        if not raw:
            raise AuthenticationFailed('Refresh token ausente.')
        try:
            token = RefreshToken(raw)
            session = (
                UserSession.objects
                .select_for_update()
                .filter(
                    refresh_jti=token['jti'],
                    is_active=True,
                    user__is_active=True,
                )
                .first()
            )
            if not session:
                raise AuthenticationFailed('Sessão revogada ou inativa.')
            serializer = TokenRefreshSerializer(data={'refresh': raw})
            serializer.is_valid(raise_exception=True)
            tokens = serializer.validated_data
            session.access_jti = AccessToken(tokens['access'])['jti']
            session.refresh_jti = RefreshToken(tokens['refresh'])['jti']
            session.save(update_fields=['access_jti', 'refresh_jti', 'last_activity'])
        except TokenError as exc:
            raise InvalidToken('Token inválido ou expirado.') from exc
        response = Response({'access': tokens['access']})
        set_auth_cookies(response, tokens)
        return response


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
        auth = CustomAuthentication()
        header = auth.get_header(request)
        raw_access = auth.get_raw_token(header) if header else request.COOKIES.get('access_token')
        if raw_access:
            try:
                token = auth.get_validated_token(raw_access)
                session = UserSession.objects.filter(access_jti=token['jti']).first()
                if session:
                    revoke_session(session)
            except (InvalidToken, TokenError):
                pass
        raw = request.COOKIES.get('refresh_token')
        if raw:
            try:
                token = RefreshToken(raw)
                UserSession.objects.filter(refresh_jti=token['jti']).update(is_active=False)
                token.blacklist()
            except TokenError:
                pass
        return clear_auth_cookies(Response({'detail': 'Logout efetuado com sucesso.'}))


class UserSessionsView(APIView):
    @extend_schema(
        tags=['Autenticação'],
        summary='Liste suas sessões',
        description='Apenas usuário autenticado; retorna dispositivos e indica a sessão atual.',
        responses={200: SESSION_RESPONSE},
    )
    def get(self, request):
        sessions = request.user.sessions.filter(is_active=True)
        return Response([
            {
                'id': session.pk,
                'device': session.device_name,
                'ip': session.ip_address,
                'created_at': session.created_at,
                'current': session.access_jti == request.auth['jti'],
            }
            for session in sessions
        ])


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
    @transaction.atomic
    def post(self, request):
        if request.user.is_staff and User.objects.filter(is_staff=True, is_active=True).count() <= 1:
            raise ValidationError('Não é possível desativar o último administrador ativo.')
        request.user.is_active = False
        request.user.save(update_fields=['is_active'])
        revoke_sessions(request.user)
        return clear_auth_cookies(Response({'detail': 'Conta desativada.'}))
