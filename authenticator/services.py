import logging

from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


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
    except Exception:
        logger.exception('Falha ao enviar e-mail de verificação para %s', email)
        return False
