"""Validação e confirmação de troca de e-mail."""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import ValidationError

from modules.accounts.mixins.tokens import check_email_token, consume_email_token
from modules.accounts.models import EmailToken

from .sessions import revoke_sessions


def verify_email_change_code(*, user, code: str, password: str | None = None) -> EmailToken:
    """Valida código de troca de e-mail antes de verificar senha atual."""
    pending = EmailToken.objects.filter(user=user, token_type=EmailToken.TokenType.NEW_EMAIL).first()
    if not pending:
        raise ValidationError({'code': 'Código inválido ou inexistente.'})
    token = check_email_token(pending.email, code, EmailToken.TokenType.NEW_EMAIL, user)
    if password is not None and not user.check_password(password):
        raise ValidationError({'password': 'Senha atual incorreta.'})
    return token


@transaction.atomic
def confirm_email_change(*, user, token: EmailToken) -> None:
    consume_email_token(token)
    if get_user_model().objects.by_email(token.email).exclude(pk=user.pk).exists():
        raise ValidationError({'new_email': 'Já existe um usuário cadastrado com este e-mail.'})
    user.email = token.email
    user.save(update_fields=['email'])
    revoke_sessions(user)
