import secrets
import string

from django.contrib.auth.hashers import check_password, make_password
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from authenticator.models.email_token import EmailToken
from authenticator.serializers.email_token import EmailTokenCreateSerializer, EmailTokenVerifySerializer
from authenticator.services import send_email_token


def generate_verification_code():
    code = ''.join(secrets.choice(string.digits) for _ in range(6))
    return code


class EmailTokenViewSet(GenericViewSet):
    def get_serializer_class(self):
        if self.action == 'verify_token':
            return EmailTokenVerifySerializer
        return EmailTokenCreateSerializer

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
        send_email_token(email, code, subject)
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
        return Response({'detail': 'Token validado!'}, status=status.HTTP_200_OK)
