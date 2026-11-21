from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers

from modules.accounts.models import EmailToken

from .email_token import EmailTokenViewSet

REGISTRATION_REQUEST = inline_serializer('RegistrationRequest', fields={'email': serializers.EmailField()})
REGISTRATION_VERIFY = inline_serializer(
    'RegistrationVerify',
    fields={
        'email': serializers.EmailField(),
        'code': serializers.CharField(min_length=6, max_length=6),
    },
)
PASSWORD_CONFIRM = inline_serializer(
    'PasswordResetConfirm',
    fields={
        'email': serializers.EmailField(),
        'code': serializers.CharField(min_length=6, max_length=6),
        'new_password': serializers.CharField(write_only=True),
    },
)


@extend_schema_view(
    create_token=extend_schema(
        tags=['Autenticação'],
        summary='Solicite código de cadastro',
        description='Público. Envia código para e-mail ainda não cadastrado, sem revelar existência de conta.',
        request=REGISTRATION_REQUEST,
        examples=[OpenApiExample('Aluno fictício', value={'email': 'aluno@exemplo.com.br'}, request_only=True)],
    ),
    verify_token=extend_schema(
        tags=['Autenticação'],
        summary='Verifique código de cadastro',
        description='Público. Confere o código sem consumi-lo; use /registration/confirm/ para criar a conta.',
        request=REGISTRATION_VERIFY,
        examples=[
            OpenApiExample(
                'Código fictício', value={'email': 'aluno@exemplo.com.br', 'code': '123456'}, request_only=True
            )
        ],
    ),
)
class RegistrationTokenViewSet(EmailTokenViewSet):
    authentication_classes = ()
    token_type = EmailToken.TokenType.NEW_USER


@extend_schema_view(
    create_token=extend_schema(
        tags=['Autenticação'],
        summary='Solicite código de recuperação',
        description='Público. Envia código de senha sem revelar existência de conta.',
        request=REGISTRATION_REQUEST,
    ),
    verify_token=extend_schema(
        tags=['Autenticação'],
        summary='Verifique código de recuperação',
        description='Público. Verifica o código sem consumi-lo.',
        request=REGISTRATION_VERIFY,
    ),
    reset_password=extend_schema(
        tags=['Autenticação'],
        summary='Confirme recuperação de senha',
        description='Público. Consome o código, altera a senha e revoga sessões existentes.',
        request=PASSWORD_CONFIRM,
        examples=[
            OpenApiExample(
                'Recuperação fictícia',
                value={
                    'email': 'aluno@exemplo.com.br',
                    'code': '123456',
                    'new_password': 'SenhaFicticia!123',
                },
                request_only=True,
            )
        ],
    ),
)
class PasswordResetTokenViewSet(RegistrationTokenViewSet):
    token_type = EmailToken.TokenType.NEW_PASSWORD
