from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.viewsets import GenericViewSet

from modules.accounts.api.serializers.email_token import (
    EmailTokenCreateSerializer,
    EmailTokenVerifySerializer,
    PasswordResetSerializer,
)
from modules.accounts.services import issue_email_token, reset_password_with_token
from shared.openapi import RESP_400_VALIDATION, RESP_429_THROTTLED, RESP_503_UNAVAILABLE


class EmailTokenViewSet(GenericViewSet):
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'email_tokens'
    token_type: str | None = None

    def get_serializer_class(self):
        if self.action == 'verify_token':
            return EmailTokenVerifySerializer
        if self.action == 'reset_password':
            return PasswordResetSerializer
        return EmailTokenCreateSerializer

    def _build_token_payload(self, request) -> dict:
        data = dict(request.data.items()) if hasattr(request.data, 'items') else dict(request.data)
        if self.token_type is not None:
            data['token_type'] = self.token_type
        return data

    @extend_schema(
        tags=['Autenticação'],
        summary='Solicite um código por e-mail',
        description=(
            'Público. Emite código de seis dígitos com prazo, limite de tentativas e intervalo de reenvio; '
            'não informa se o e-mail está cadastrado.'
        ),
        request=EmailTokenCreateSerializer,
        responses={
            200: {'type': 'object', 'properties': {'detail': {'type': 'string'}}},
            400: RESP_400_VALIDATION,
            429: RESP_429_THROTTLED,
            503: RESP_503_UNAVAILABLE,
        },
        examples=[
            OpenApiExample(
                'Solicitação fictícia',
                value={'email': 'aluno@exemplo.com.br', 'token_type': 'new-user'},
                request_only=True,
            ),
            OpenApiExample(
                'Solicitação recebida',
                value={'detail': 'E-mail enviado com sucesso!'},
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    @action(detail=False, methods=['post'], url_path='send-email')
    def create_token(self, request):
        serializer = self.get_serializer(data=self._build_token_payload(request))
        serializer.is_valid(raise_exception=True)
        delivered = issue_email_token(
            email=serializer.validated_data['email'],
            token_type=serializer.validated_data['token_type'],
            user=request.user if request.user.is_authenticated else None,
        )
        if not delivered:
            return Response(
                {'detail': 'Não foi possível enviar o e-mail. Tente novamente em instantes.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'detail': 'E-mail enviado com sucesso!'}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Autenticação'],
        summary='Verifique o código',
        description='Público. Confere o código mais recente, validade e limite de tentativas; não consome o código.',
        request=EmailTokenVerifySerializer,
        responses={
            200: {'type': 'object', 'properties': {'message': {'type': 'string'}}},
            400: RESP_400_VALIDATION,
            429: RESP_429_THROTTLED,
        },
        examples=[
            OpenApiExample(
                'Código fictício',
                value={'email': 'aluno@exemplo.com.br', 'code': '123456', 'token_type': 'new-user'},
                request_only=True,
            )
        ],
    )
    @action(detail=False, methods=['post'], url_path='verify-token')
    def verify_token(self, request):
        serializer = self.get_serializer(data=self._build_token_payload(request))
        serializer.is_valid(raise_exception=True)
        return Response({'message': 'Válido'})

    @extend_schema(
        tags=['Autenticação'],
        summary='Redefina a senha com código',
        description='Público. Consome código de recuperação, redefine senha com hashing e revoga sessões do usuário.',
        request=PasswordResetSerializer,
        responses={
            200: {'type': 'object', 'properties': {'detail': {'type': 'string'}}},
            400: RESP_400_VALIDATION,
            429: RESP_429_THROTTLED,
        },
    )
    @action(detail=False, methods=['post'], url_path='reset-password')
    def reset_password(self, request):
        # Validação fica fora da transação para preservar incremento de tentativas inválidas.
        payload = self._build_token_payload(request)
        if 'new_password' in payload and 'password' not in payload:
            payload['password'] = payload['new_password']
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        updated = reset_password_with_token(
            email=serializer.validated_data['email'],
            token=serializer.context['token_instance'],
            password=serializer.validated_data['password'],
        )
        if not updated:
            return Response({'detail': 'Código inválido ou inexistente.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Senha redefinida com sucesso.'}, status=status.HTTP_200_OK)
