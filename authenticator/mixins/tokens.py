from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers

from authenticator.models.email_token import EmailToken


def check_email_token(email, code, token_type):
    """
    Valida o código mais recente enviado para o e-mail. Códigos expiram e são invalidados
    após várias tentativas erradas, impedindo descobrir o código de 6 dígitos por força bruta.
    """
    token = (
        EmailToken.objects.filter(email__iexact=email, token_type=token_type).order_by('-created_at').first()
    )

    if not token:
        raise serializers.ValidationError({'code': 'Código inválido ou inexistente.'})

    if token.consumed:
        raise serializers.ValidationError({'code': 'Este código já foi utilizado.'})

    if timezone.now() > token.created_at + timedelta(minutes=settings.EMAIL_TOKEN_EXPIRATION_MINUTES):
        raise serializers.ValidationError({'code': 'Este código expirou. Solicite um novo código.'})

    if token.failed_attempts >= settings.EMAIL_TOKEN_MAX_ATTEMPTS:
        raise serializers.ValidationError({'code': 'Número máximo de tentativas excedido. Solicite um novo código.'})

    if not code or not check_password(code, token.token_hash):
        EmailToken.objects.filter(pk=token.pk).update(failed_attempts=F('failed_attempts') + 1)
        raise serializers.ValidationError({'code': 'Código inválido ou inexistente.'})

    return token


class TokenValidatorMixin:
    def validate_token(self, email, code, token_type):
        if not email:
            raise serializers.ValidationError(
                {'email': 'O e-mail é obrigatório para validar o código.'},
            )

        return check_email_token(email, code, token_type)
