from django.contrib.auth.hashers import check_password
from rest_framework import serializers

from authenticator.models.email_token import EmailToken


class TokenValidatorMixin:
    def validate_token(self, email, code, token_type):
        if not email:
            raise serializers.ValidationError(
                {'email': 'O e-mail é obrigatório para validar o código.'},
            )

        token = EmailToken.objects.filter(email=email, token_type=token_type).order_by('-created_at').first()

        if not token or not check_password(code, token.token_hash):
            raise serializers.ValidationError(
                {'code': 'Código inválido ou inexistente.'},
            )

        if token.consumed:
            raise serializers.ValidationError(
                {'code': 'Este código já foi utilizado.'},
            )

        return token
