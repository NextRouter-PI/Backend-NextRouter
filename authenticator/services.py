import logging

from django.core.mail import EmailMessage

# TODO - Criar template HTML estilizado para o email.

logger = logging.getLogger(__name__)


def send_email_token(email, code, subject):
    message = EmailMessage(subject=subject, body=code, to=[email])
    try:
        message.send()
        return True
    except Exception:
        logger.exception('Falha ao enviar e-mail de verificação para %s', email)
        return False
