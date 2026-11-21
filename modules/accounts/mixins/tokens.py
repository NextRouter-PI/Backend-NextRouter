from rest_framework import serializers

from modules.accounts.models.email_token import EmailToken


def check_email_token(email, code, token_type, user=None):
    """
    Valida o código mais recente enviado para o e-mail. Códigos expiram e são invalidados
    após várias tentativas erradas, impedindo descobrir o código de 6 dígitos por força bruta.
    """
    tokens = EmailToken.objects.filter(email__iexact=email, token_type=token_type)
    if token_type == EmailToken.TokenType.NEW_EMAIL:
        if not user or not user.is_authenticated:
            raise serializers.ValidationError({'code': 'Código inválido ou inexistente.'})
        tokens = tokens.filter(user=user)
    token = tokens.order_by('-created_at').first()

    if not token:
        raise serializers.ValidationError({'code': 'Código inválido ou inexistente.'})

    if token.consumed:
        raise serializers.ValidationError({'code': 'Este código já foi utilizado.'})

    if token.is_expired():
        raise serializers.ValidationError({'code': 'Este código expirou. Solicite um novo código.'})

    if token.is_blocked():
        raise serializers.ValidationError({'code': 'Número máximo de tentativas excedido. Solicite um novo código.'})

    if not code or not token.verify_code(code):
        raise serializers.ValidationError({'code': 'Código inválido ou inexistente.'})

    return token


def consume_email_token(token):
    # A atualização condicional impede duas confirmações simultâneas com o mesmo código.
    if not token.consume_atomically():
        raise serializers.ValidationError({'code': 'Este código já foi utilizado.'})


class TokenValidatorMixin:
    def validate_token(self, email, code, token_type):
        if not email:
            raise serializers.ValidationError(
                {'email': 'O e-mail é obrigatório para validar o código.'},
            )

        request = self.context.get('request')
        return check_email_token(email, code, token_type, getattr(request, 'user', None))
