from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from modules.accounts.api.serializers.email_change import EmailChangeCodeSerializer, EmailChangeConfirmSerializer
from modules.accounts.api.views.email_token import EmailTokenViewSet
from modules.accounts.http import clear_auth_cookies
from modules.accounts.models import EmailToken
from modules.accounts.services import confirm_email_change, verify_email_change_code
from shared.openapi import RESP_400_VALIDATION, RESP_401_UNAUTHORIZED


@extend_schema_view(
    create_token=extend_schema(
        tags=['Autenticação'],
        summary='Solicite código para novo e-mail',
        description=(
            'Usuário autenticado. Envia código ao novo endereço sem revelar se já há conta; '
            'confirmação exige senha atual.'
        ),
        request=inline_serializer(
            'EmailChangeRequest',
            fields={'new_email': serializers.EmailField()},
        ),
    )
)
class EmailChangeViewSet(EmailTokenViewSet):
    permission_classes = (IsAuthenticated,)
    token_type = EmailToken.TokenType.NEW_EMAIL

    def _build_token_payload(self, request) -> dict:
        return {'email': request.data.get('new_email'), 'token_type': self.token_type}

    @extend_schema(
        tags=['Autenticação'],
        summary='Verifique código do novo e-mail',
        description='Usuário autenticado. Confere código de troca do próprio e-mail; não consome o código.',
        request=EmailChangeCodeSerializer,
        responses={
            200: inline_serializer('EmailChangeVerifyResponse', fields={'detail': serializers.CharField()}),
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
        },
    )
    def verify_token(self, request):
        serializer = EmailChangeCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verify_email_change_code(user=request.user, code=serializer.validated_data['code'])
        return Response({'detail': 'Código válido.'})

    @extend_schema(
        tags=['Autenticação'],
        summary='Confirme o novo e-mail',
        description='Usuário autenticado. Exige código e senha atual, altera e-mail e revoga todas as sessões.',
        request=EmailChangeConfirmSerializer,
        responses={
            200: inline_serializer('EmailChangeDoneResponse', fields={'detail': serializers.CharField()}),
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
        },
    )
    def confirm(self, request):
        serializer = EmailChangeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = verify_email_change_code(
            user=request.user,
            code=serializer.validated_data['code'],
            password=serializer.validated_data['password'],
        )
        confirm_email_change(user=request.user, token=token)
        return clear_auth_cookies(Response({'detail': 'E-mail alterado. Faça login novamente.'}))
