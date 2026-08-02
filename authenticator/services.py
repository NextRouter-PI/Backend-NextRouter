from django.core.mail import EmailMessage


def send_email_token(email, code, subject):
    email = EmailMessage(subject=subject, body=code, to=[email])
    return email.send()
