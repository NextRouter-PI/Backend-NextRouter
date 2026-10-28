import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone
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
from modules.accounts.mixins.tokens import consume_email_token
from modules.accounts.models import User
from modules.accounts.models.email_token import EmailToken
from modules.accounts.services import revoke_sessions, send_email_token
from shared.openapi import RESP_400_VALIDATION, RESP_429_THROTTLED, RESP_503_UNAVAILABLE

EMAIL_SUBJECTS = {
    EmailToken.TokenType.NEW_PASSWORD: 'NextRouter - Código para redefinir sua senha',
    EmailToken.TokenType.NEW_USER: 'NextRouter - Código de verificação do cadastro',
    EmailToken.TokenType.NEW_EMAIL: 'NextRouter - Código de verificação do novo e-mail',
}


def generate_verification_code():
    return ''.join(secrets.choice(string.digits) for _ in range(6))


class EmailTokenViewSet(GenericViewSet):
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'email_tokens'

    def get_serializer_class(self):
        if self.action == 'verify_token':
            return EmailTokenVerifySerializer
        if self.action == 'reset_password':
            return PasswordResetSerializer
        return EmailTokenCreateSerializer

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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        token_type = serializer.validated_data['token_type']
        success_response = Response({'detail': 'E-mail enviado com sucesso!'}, status=status.HTTP_200_OK)

        # Não revela se o e-mail está cadastrado: responde com sucesso sem enviar nada.
        exists = User.objects.filter(email__iexact=email).exists()
        if (token_type == EmailToken.TokenType.NEW_PASSWORD and not exists) or (
            token_type in {EmailToken.TokenType.NEW_USER, EmailToken.TokenType.NEW_EMAIL} and exists
        ):
            return success_response

        if EmailToken.objects.filter(
            email__iexact=email,
            token_type=token_type,
            created_at__gte=timezone.now() - timedelta(seconds=settings.EMAIL_TOKEN_RESEND_SECONDS),
        ).exists():
            return success_response

        code = generate_verification_code()
        with transaction.atomic():
            if token_type == EmailToken.TokenType.NEW_EMAIL:
                EmailToken.objects.filter(user=request.user, token_type=token_type).update(consumed=True)
            serializer.save(
                token_hash=make_password(code),
                user=request.user if token_type == EmailToken.TokenType.NEW_EMAIL else None,
            )
            if not send_email_token(email, code, EMAIL_SUBJECTS[token_type]):
                transaction.set_rollback(True)
                if token_type == EmailToken.TokenType.NEW_EMAIL:
                    return Response(
                        {'detail': 'Não foi possível enviar o e-mail. Tente novamente em instantes.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                return success_response

        return success_response

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
        serializer = self.get_serializer(data=request.data)
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
        # A validação fica fora da transação para que o contador de tentativas inválidas
        # do código não seja desfeito (rollback) quando a validação falhar.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(email__iexact=serializer.validated_data['email']).first()
        if not user:
            return Response({'detail': 'Código inválido ou inexistente.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            consume_email_token(serializer.context['token_instance'])
            user.set_password(serializer.validated_data['password'])
            user.save(update_fields=['password'])
            revoke_sessions(user)

        return Response({'detail': 'Senha redefinida com sucesso.'}, status=status.HTTP_200_OK)
