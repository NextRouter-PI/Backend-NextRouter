from django.db import transaction
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from modules.accounts.api.views.email_token import EmailTokenViewSet
from modules.accounts.mixins.tokens import check_email_token, consume_email_token
from modules.accounts.models import EmailToken, User
from modules.accounts.services import revoke_sessions
from shared.openapi import RESP_400_VALIDATION, RESP_401_UNAUTHORIZED


class EmailChangeCodeSerializer(serializers.Serializer):
    code = serializers.RegexField(r'^\d{6}$')


class EmailChangeConfirmSerializer(EmailChangeCodeSerializer):
    password = serializers.CharField(write_only=True)


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

    def get_serializer(self, *args, **kwargs):
        if self.action == 'create_token' and 'data' in kwargs:
            data = kwargs['data'].copy()
            data['email'] = data.get('new_email')
            data['token_type'] = 'new-email'
            kwargs['data'] = data
        return super().get_serializer(*args, **kwargs)

    def validate_code(self, request, confirm=False):
        serializer_class = EmailChangeConfirmSerializer if confirm else EmailChangeCodeSerializer
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        if confirm and not request.user.check_password(serializer.validated_data['password']):
            raise ValidationError({'password': 'Senha atual incorreta.'})
        pending = EmailToken.objects.filter(user=request.user, token_type='new-email').first()
        if not pending:
            raise ValidationError({'code': 'Código inválido ou inexistente.'})
        return check_email_token(pending.email, serializer.validated_data['code'], 'new-email', request.user)

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
        self.validate_code(request)
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
        token = self.validate_code(request, confirm=True)
        with transaction.atomic():
            consume_email_token(token)
            if User.objects.filter(email__iexact=token.email).exclude(pk=request.user.pk).exists():
                raise ValidationError({'new_email': 'Já existe um usuário cadastrado com este e-mail.'})
            request.user.email = token.email
            request.user.save(update_fields=['email'])
            revoke_sessions(request.user)
        return Response({'detail': 'E-mail alterado. Faça login novamente.'})
