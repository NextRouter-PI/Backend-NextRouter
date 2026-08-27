import secrets
import string

from django.contrib.auth.hashers import check_password, make_password
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from authenticator.models import User
from authenticator.models.email_token import EmailToken
from authenticator.serializers.email_token import (
    EmailTokenCreateSerializer,
    EmailTokenVerifySerializer,
    PasswordResetSerializer,
)
from authenticator.services import send_email_token


def generate_verification_code():
    code = ''.join(secrets.choice(string.digits) for _ in range(6))
    return code


class EmailTokenViewSet(GenericViewSet):
    def get_serializer_class(self):
        if self.action == 'verify_token':
            return EmailTokenVerifySerializer
        if self.action == 'reset_password':
            return PasswordResetSerializer
        return EmailTokenCreateSerializer

    def get_permissions(self):
        return [AllowAny()]

    @action(detail=False, methods=['post'], url_path='send-email')
    def create_token(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = generate_verification_code()
        token_hash = make_password(code)
        serializer.save(token_hash=token_hash)
        email = request.data['email']
        token_type = request.data['token_type']
        if token_type == 'new-password':
            subject = 'Código de verificação de nova senha.'
        if token_type == 'new-user':
            subject = 'Código de verificação de novo usuário.'
        if token_type == 'new-email':
            subject = 'Código de verificação de novo email'

        if not send_email_token(email, code, subject):
            return Response(
                {'detail': 'Não foi possível enviar o e-mail. Tente novamente em instantes.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({'detail': 'E-mail enviado com sucesso!'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='verify-token')
    def verify_token(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = request.data['email']
        code = request.data['code']
        token_obj = EmailToken.objects.filter(email=email).last()
        if token_obj and check_password(code, token_obj.token_hash):
            return Response({'message': 'Válido'})
        return Response({'detail': 'Código inválido.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='reset-password')
    def reset_password(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.filter(email=serializer.validated_data['email']).first()
        if not user:
            return Response({'detail': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        user.set_password(serializer.validated_data['password'])
        user.save(update_fields=['password'])

        token = serializer.context.get('token_instance')
        token.consumed = True
        token.save(update_fields=['consumed'])

        return Response({'detail': 'Senha redefinida com sucesso.'}, status=status.HTTP_200_OK)
