"""Backends HTTP simples para envio de e-mail em ambientes sem SMTP de saída."""

from email.utils import parseaddr

import httpx
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


def _parse_address(raw: str) -> dict[str, str]:
    name, address = parseaddr(raw)
    entry = {'email': address or raw.strip()}
    if name:
        entry['name'] = name
    return entry


class BrevoEmailBackend(BaseEmailBackend):
    """Envia mensagens via API HTTP v3 do Brevo usando httpx."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, 'BREVO_API_KEY', '').strip()
        if not api_key:
            if not self.fail_silently:
                raise ValueError('BREVO_API_KEY não configurada.')
            return 0

        timeout = getattr(settings, 'EMAIL_TIMEOUT', 15)
        headers = {
            'api-key': api_key,
            'accept': 'application/json',
            'content-type': 'application/json',
        }

        sent = 0
        with httpx.Client(timeout=timeout) as client:
            for message in email_messages:
                if not message.to:
                    continue

                payload = {
                    'sender': _parse_address(message.from_email or settings.DEFAULT_FROM_EMAIL),
                    'to': [_parse_address(addr) for addr in message.to],
                    'subject': message.subject,
                }
                if message.cc:
                    payload['cc'] = [_parse_address(addr) for addr in message.cc]
                if message.bcc:
                    payload['bcc'] = [_parse_address(addr) for addr in message.bcc]
                if message.reply_to:
                    payload['replyTo'] = _parse_address(message.reply_to[0])

                html_body = next(
                    (content for content, mimetype in getattr(message, 'alternatives', ()) if mimetype == 'text/html'),
                    None,
                )
                if html_body:
                    payload['htmlContent'] = html_body
                if message.body:
                    payload['textContent'] = message.body

                try:
                    response = client.post(BREVO_API_URL, headers=headers, json=payload)
                    response.raise_for_status()
                except Exception:
                    if not self.fail_silently:
                        raise
                    continue
                sent += 1

        return sent
