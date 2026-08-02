from django.core.mail import EmailMessage

# TODO - Criar template HTML estilizado para o email.


def send_email_token(email, code, subject):
    email = EmailMessage(subject=subject, body=code, to=[email])
    return email.send()  # TODO - Transformar em try/except
