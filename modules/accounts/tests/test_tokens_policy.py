from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.utils import timezone

from modules.accounts.models import EmailToken
from tests.helpers import BaseAPITestCase, create_user


class EmailTokenPolicyTests(BaseAPITestCase):
    def test_signup_request_does_not_reveal_registered_email(self):
        create_user('registered@example.com')
        responses = [
            self.client.post('/api/registration/request/', {'email': email})
            for email in ('registered@example.com', 'new@example.com')
        ]
        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertEqual(responses[0].data, responses[1].data)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_is_delayed_for_same_address(self):
        url = '/api/registration/request/'
        self.assertEqual(self.client.post(url, {'email': 'new@example.com'}).status_code, 200)
        self.assertEqual(self.client.post(url, {'email': 'new@example.com'}).status_code, 200)
        self.assertEqual(EmailToken.objects.filter(email='new@example.com').count(), 1)
        self.assertEqual(len(mail.outbox), 1)

        EmailToken.objects.filter(email='new@example.com').update(created_at=timezone.now() - timedelta(minutes=2))
        self.assertEqual(self.client.post(url, {'email': 'new@example.com'}).status_code, 200)
        self.assertEqual(EmailToken.objects.filter(email='new@example.com').count(), 2)

    def test_mail_failure_does_not_reveal_whether_reset_user_exists(self):
        create_user('registered@example.com')
        with patch('modules.accounts.api.views.email_token.send_email_token', return_value=False):
            existing = self.client.post('/api/password-reset/request/', {'email': 'registered@example.com'})
        unknown = self.client.post('/api/password-reset/request/', {'email': 'unknown@example.com'})
        self.assertEqual(existing.status_code, unknown.status_code)
        self.assertEqual(existing.data, unknown.data)
        self.assertFalse(EmailToken.objects.filter(email='registered@example.com').exists())
