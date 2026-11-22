"""Emissão de códigos por e-mail e redefinição de senha."""

import logging
import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from rest_framework.exceptions import ValidationError

from modules.accounts.mixins.tokens import consume_email_token
from modules.accounts.models import EmailToken

from .sessions import revoke_sessions

logger = logging.getLogger(__name__)

EMAIL_SUBJECTS = {
    EmailToken.TokenType.NEW_PASSWORD: 'NextRouter - Código para redefinir sua senha',
    EmailToken.TokenType.NEW_USER: 'NextRouter - Código de verificação do cadastro',
    EmailToken.TokenType.NEW_EMAIL: 'NextRouter - Código de verificação do novo e-mail',
}

EMAIL_TOKEN_COPY = {
    EmailToken.TokenType.NEW_USER: {
        'badge': 'Cadastro',
        'heading': 'Confirme seu e-mail',
        'intro': (
            'Use o código abaixo para concluir a verificação do seu e-mail '
            'e finalizar a criação da sua conta no NextRouter.'
        ),
        'security_note': (
            'Se você não iniciou um cadastro no NextRouter, ignore este e-mail. '
            'Nunca compartilhe este código com terceiros.'
        ),
    },
    EmailToken.TokenType.NEW_PASSWORD: {
        'badge': 'Recuperação',
        'heading': 'Redefina sua senha',
        'intro': (
            'Recebemos uma solicitação para redefinir a senha da sua conta. '
            'Digite o código abaixo para continuar; ao confirmar, suas sessões anteriores serão encerradas.'
        ),
        'security_note': (
            'Se você não solicitou a redefinição de senha, ignore este e-mail com segurança. '
            'Sua senha atual permanece inalterada.'
        ),
    },
    EmailToken.TokenType.NEW_EMAIL: {
        'badge': 'Troca de e-mail',
        'heading': 'Confirme seu novo e-mail',
        'intro': (
            'Digite o código abaixo para confirmar a alteração do endereço de e-mail da sua conta no NextRouter. '
            'Ao concluir, suas sessões anteriores serão encerradas.'
        ),
        'security_note': 'Se você não solicitou esta alteração, ignore este e-mail e revise a segurança da sua conta.',
    },
}

DEFAULT_EMAIL_TOKEN_COPY = {
    'badge': 'Verificação',
    'heading': 'Seu código de verificação',
    'intro': 'Use o código abaixo para concluir sua verificação de segurança no NextRouter.',
    'security_note': (
        'Se você não solicitou este código, ignore este e-mail. Nunca compartilhe este código com terceiros.'
    ),
}


def generate_verification_code() -> str:
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def send_email_token(email: str, code: str, subject: str, *, token_type: str | None = None) -> bool:
    minutes = getattr(settings, 'EMAIL_TOKEN_EXPIRATION_MINUTES', 15)
    copy = EMAIL_TOKEN_COPY.get(token_type, DEFAULT_EMAIL_TOKEN_COPY)
    context = {
        'subject': subject,
        'code': code,
        'expiration_minutes': minutes,
        **copy,
    }
    text_body = render_to_string('emails/verification_code.txt', context)
    html_body = render_to_string('emails/verification_code.html', context)

    message = EmailMultiAlternatives(subject=subject, body=text_body, to=[email])
    message.attach_alternative(html_body, 'text/html')
    try:
        message.send()
        return True
    except Exception as exc:
        logger.warning(
            'email_token_delivery_failed reason=%s',
            type(exc).__name__,
            extra={'op_event': 'email_delivery_failed'},
        )
        return False


def issue_email_token(*, email: str, token_type: str, user=None) -> bool:
    """Emite código de 6 dígitos respeitando anti-enumeração e cooldown.

    Retorna False apenas quando `NEW_EMAIL` falha na entrega SMTP (sinalizando 503).
    """
    if token_type == EmailToken.TokenType.NEW_EMAIL and (user is None or getattr(user, 'pk', None) is None):
        raise ValidationError({'detail': 'Usuário autenticado é obrigatório para troca de e-mail.'})

    user_model = get_user_model()
    exists = user_model.objects.by_email(email).exists()
    if (token_type == EmailToken.TokenType.NEW_PASSWORD and not exists) or (
        token_type in {EmailToken.TokenType.NEW_USER, EmailToken.TokenType.NEW_EMAIL} and exists
    ):
        return True

    if EmailToken.objects.in_cooldown(email=email, token_type=token_type).exists():
        return True

    code = generate_verification_code()
    token = EmailToken.objects.create(
        email=email,
        token_type=token_type,
        token_hash=make_password(code),
        user=user if token_type == EmailToken.TokenType.NEW_EMAIL else None,
    )
    # Envio SMTP fora de transação para evitar segurar conexão/locks em I/O de rede.
    if not send_email_token(email, code, EMAIL_SUBJECTS[token_type], token_type=token_type):
        token.delete()
        return token_type != EmailToken.TokenType.NEW_EMAIL

    if token_type == EmailToken.TokenType.NEW_EMAIL:
        EmailToken.objects.filter(user=user, token_type=token_type).exclude(pk=token.pk).update(consumed=True)
    return True


@transaction.atomic
def reset_password_with_token(*, email: str, token: EmailToken, password: str) -> bool:
    user = get_user_model().objects.by_email(email).first()
    if not user:
        return False
    consume_email_token(token)
    user.set_password(password)
    user.save(update_fields=['password'])
    revoke_sessions(user)
    return True
