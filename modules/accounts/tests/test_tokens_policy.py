from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.utils import timezone

from modules.accounts.models import EmailToken
from tests.helpers import BaseAPITestCase, create_user


class EmailTokenPolicyTests(BaseAPITestCase):
    def verify(self, email, code):
        return self.client.post('/api/registration/verify/', {'email': email, 'code': code}, format='json')

    def test_code_is_blocked_after_max_attempts(self):
        code = self.request_code('ana@example.com')
        wrong = '111111' if code == '000000' else '000000'
        for _ in range(5):
            self.assertEqual(self.verify('ana@example.com', wrong).status_code, 400)
        self.assertEqual(self.verify('ana@example.com', code).status_code, 400)

    def test_expired_code_is_rejected(self):
        code = self.request_code('ana@example.com')
        EmailToken.objects.update(created_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(self.verify('ana@example.com', code).status_code, 400)

    def test_verify_uses_latest_code(self):
        with patch('modules.accounts.services.generate_verification_code', side_effect=['123456', '654321']):
            previous = self.request_code('ana@example.com')
            EmailToken.objects.filter(email='ana@example.com').update(created_at=timezone.now() - timedelta(minutes=2))
            latest = self.request_code('ana@example.com')
        self.assertEqual(self.verify('ana@example.com', previous).status_code, 400)
        self.assertEqual(self.verify('ana@example.com', latest).status_code, 200)

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
        with patch('modules.accounts.services.send_email_token', return_value=False):
            existing = self.client.post('/api/password-reset/request/', {'email': 'registered@example.com'})
        unknown = self.client.post('/api/password-reset/request/', {'email': 'unknown@example.com'})
        self.assertEqual(existing.status_code, unknown.status_code)
        self.assertEqual(existing.data, unknown.data)
        self.assertFalse(EmailToken.objects.filter(email='registered@example.com').exists())
        self.assertEqual(len(mail.outbox), 0)
