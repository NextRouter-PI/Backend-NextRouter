import secrets
import string

from django.contrib.auth.hashers import make_password
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.viewsets import GenericViewSet

from authenticator.models import User
from authenticator.models.email_token import EmailToken
from authenticator.serializers.email_token import (
    EmailTokenCreateSerializer,
    EmailTokenVerifySerializer,
    PasswordResetSerializer,
)
from authenticator.services import send_email_token

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

    @action(detail=False, methods=['post'], url_path='send-email')
    def create_token(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        token_type = serializer.validated_data['token_type']
        success_response = Response({'detail': 'E-mail enviado com sucesso!'}, status=status.HTTP_200_OK)

        # Não revela se o e-mail está cadastrado: responde com sucesso sem enviar nada.
        if token_type == EmailToken.TokenType.NEW_PASSWORD and not User.objects.filter(email__iexact=email).exists():
            return success_response

        code = generate_verification_code()
        serializer.save(token_hash=make_password(code))

        if not send_email_token(email, code, EMAIL_SUBJECTS[token_type]):
            return Response(
                {'detail': 'Não foi possível enviar o e-mail. Tente novamente em instantes.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return success_response

    @action(detail=False, methods=['post'], url_path='verify-token')
    def verify_token(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'message': 'Válido'})

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
            user.set_password(serializer.validated_data['password'])
            user.save(update_fields=['password'])

            token = serializer.context['token_instance']
            token.consumed = True
            token.save(update_fields=['consumed'])

        return Response({'detail': 'Senha redefinida com sucesso.'}, status=status.HTTP_200_OK)
