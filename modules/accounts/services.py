import logging

from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


def revoke_sessions(user):
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    user.sessions.filter(is_active=True).update(is_active=False)
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def revoke_session(session):
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    token = OutstandingToken.objects.filter(jti=session.refresh_jti).first()
    if token:
        BlacklistedToken.objects.get_or_create(token=token)
    session.is_active = False
    session.save(update_fields=['is_active'])


def send_email_token(email, code, subject):
    body = (
        'Olá!\n\n'
        f'Seu código de verificação do NextRouter é: {code}\n\n'
        'O código é válido por 15 minutos. Se você não solicitou este código, ignore este e-mail.\n'
    )
    message = EmailMessage(subject=subject, body=body, to=[email])
    try:
        message.send()
        return True
    except Exception as exc:
        logger.warning('email_token_delivery_failed reason=%s', type(exc).__name__)
        return False
