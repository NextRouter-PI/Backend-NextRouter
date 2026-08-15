from django.contrib.auth.hashers import check_password
from rest_framework import serializers

from authenticator.models.email_token import EmailToken

# Classe Mixin, que serve para validar os códigos (tokens) enviados nas requisições que os usuário recebem no email


class TokenValidatorMixin:
    def validate_token(self, email: str | None, code: str, token_type: str) -> EmailToken:
        if not email:
            raise serializers.ValidationError(
                {'email': 'O e-mail é obrigatório para validar o código.'},
            )

        # Busca o token relacionado ao email do usuádio mais recente pelo tipo
        token = EmailToken.objects.filter(email=email, token_type=token_type).order_by('-created_at').first()

        # Se o token não existe no banco ou o hash não bateu, envia um erro
        if not token or not check_password(code, token.token_hash):
            raise serializers.ValidationError(
                {'code': 'Código inválido ou inexistente.'},
            )

        # Se já foi usado também envia um erro
        if token.consumed:
            raise serializers.ValidationError(
                {'code': 'Este código já foi utilizado.'},
            )

        # Retorna token para ser salvo no contexto
        return token
