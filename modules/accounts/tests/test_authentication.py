import re
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from modules.accounts.models import EmailToken, User, UserSession
from modules.organizations.models import Passenger
from tests.helpers import PASSWORD, BaseAPITestCase, create_user, masked_cpf


class AuthenticationTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user('ana@example.com')

    def login(self, client=None):
        client = client or self.client
        response = client.post('/api/login/', {'email': self.user.email, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['access']

    def code(self, url, data):
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)

    def test_login_creates_session_with_refresh_expiry_and_rejects_wrong_password(self):
        before = timezone.now()
        response = self.client.post('/api/login/', {'email': self.user.email, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.data)
        session = UserSession.objects.get(user=self.user)
        self.assertEqual(session.access_jti, AccessToken(response.data['access'])['jti'])
        self.assertLessEqual(
            abs(session.expires_at - (before + settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'])),
            timedelta(seconds=30),
        )
        denied = APIClient().post('/api/login/', {'email': self.user.email, 'password': 'wrong'})
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(UserSession.objects.filter(user=self.user).count(), 1)

    def test_refresh_rotates_and_logout_revokes_access_and_refresh(self):
        old_access = self.login()
        old_refresh = self.client.cookies['refresh_token'].value
        response = self.client.post('/api/refresh/')
        self.assertEqual(response.status_code, 200, response.data)
        access = response.data['access']
        refresh = self.client.cookies['refresh_token'].value
        self.assertNotEqual(old_refresh, refresh)
        attacker = APIClient()
        attacker.cookies['refresh_token'] = old_refresh
        self.assertEqual(attacker.post('/api/refresh/').status_code, 401)
        attacker.credentials(HTTP_AUTHORIZATION=f'Bearer {old_access}')
        self.assertEqual(attacker.get('/api/users/me/').status_code, 401)
        self.assertEqual(self.client.post('/api/me/logout/').status_code, 200)
        self.assertEqual(self.client.cookies['access_token'].value, '')
        self.assertEqual(self.client.cookies['refresh_token'].value, '')
        attacker.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(attacker.get('/api/users/me/').status_code, 401)
        attacker.cookies['refresh_token'] = refresh
        self.assertEqual(attacker.post('/api/refresh/').status_code, 401)

    def test_sessions_ownership_current_and_revocation(self):
        self.login()
        other_device = APIClient()
        self.login(other_device)
        sessions = self.client.get('/api/sessions/').data
        self.assertEqual(len(sessions), 2)
        self.assertTrue(all(uuid.UUID(str(session['id'])) for session in sessions))
        current = next(session for session in sessions if session['current'])
        other = next(session for session in sessions if not session['current'])
        self.assertEqual(self.client.delete(f'/api/sessions/{current["id"]}/').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/sessions/{other["id"]}/').status_code, 200)
        self.assertEqual(other_device.get('/api/users/me/').status_code, 401)
        stranger = create_user('stranger@example.com')
        foreign = UserSession.objects.create(
            user=stranger, access_jti='foreign', refresh_jti='foreign', expires_at=timezone.now() + timedelta(days=1)
        )
        self.assertEqual(self.client.delete(f'/api/sessions/{foreign.pk}/').status_code, 404)
        self.assertEqual(self.client.post('/api/me/revoke-sessions/').status_code, 200)
        self.assertFalse(self.user.sessions.filter(is_active=True).exists())

    def test_csrf_for_login_cookie_writes_refresh_and_logout(self):
        client = APIClient(enforce_csrf_checks=True)
        credentials = {'email': self.user.email, 'password': PASSWORD}
        self.assertEqual(client.post('/api/login/', credentials).status_code, 403)
        csrf = client.get('/api/csrf/').data['csrfToken']
        self.assertEqual(client.post('/api/login/', credentials, HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        self.assertEqual(client.get('/api/users/me/').status_code, 200)
        for url in ('/api/refresh/', '/api/me/logout/', '/api/me/revoke-sessions/'):
            self.assertEqual(client.post(url).status_code, 403)
        self.assertTrue(self.user.sessions.filter(is_active=True).exists())
        self.assertEqual(client.patch('/api/users/me/', {'name': 'Novo nome'}).status_code, 403)
        self.assertEqual(client.post('/api/refresh/', HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        self.assertEqual(client.post('/api/me/logout/', HTTP_X_CSRFTOKEN=csrf).status_code, 200)

    def test_password_reset_revokes_sessions_and_code_cannot_be_reused(self):
        self.login()
        code = self.code('/api/password-reset/request/', {'email': self.user.email})
        payload = {'email': self.user.email, 'code': code, 'new_password': 'OutraSenha@456'}
        self.assertEqual(self.client.post('/api/password-reset/verify/', payload).status_code, 200)
        self.assertEqual(self.client.post('/api/password-reset/confirm/', payload).status_code, 200)
        self.assertFalse(self.user.sessions.filter(is_active=True).exists())
        self.assertEqual(self.client.post('/api/password-reset/confirm/', payload).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(payload['new_password']))

    def test_email_change_requires_password_and_revokes_sessions(self):
        self.login()
        code = self.code('/api/email-change/request/', {'new_email': 'new@example.com'})
        self.assertEqual(self.client.post('/api/email-change/verify/', {'code': code}).status_code, 200)
        self.assertEqual(
            self.client.post('/api/email-change/confirm/', {'code': code, 'password': 'wrong'}).status_code, 400
        )
        response = self.client.post('/api/email-change/confirm/', {'code': code, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@example.com')
        self.assertFalse(self.user.sessions.filter(is_active=True).exists())

    def test_registration_preserves_profile_fields_and_consumes_code(self):
        code = self.code('/api/registration/request/', {'email': 'new@example.com'})
        self.assertFalse(User.objects.filter(email='new@example.com').exists())
        self.assertEqual(
            self.client.post('/api/registration/verify/', {'email': 'new@example.com', 'code': code}).status_code, 200
        )
        payload = {
            'type': 'passenger',
            'user_data': {
                'email': 'new@example.com',
                'code': code,
                'password': PASSWORD,
                'name': 'Nova Pessoa',
                'cpf': masked_cpf(),
                'phone': '47999990000',
                'birthday': '2000-05-15',
            },
        }
        response = self.client.post('/api/registration/confirm/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        passenger = Passenger.objects.get(user__email='new@example.com')
        self.assertEqual(passenger.user.phone, '47999990000')
        self.assertEqual(len(passenger.user.cpf), 11)
        self.assertTrue(EmailToken.objects.get(email='new@example.com').consumed)

    def test_failed_delivery_rolls_back_code(self):
        with patch('modules.accounts.api.views.email_token.send_email_token', return_value=False):
            response = self.client.post('/api/registration/request/', {'email': 'new@example.com'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EmailToken.objects.filter(email='new@example.com').exists())

    def test_email_code_cannot_be_used_by_another_account(self):
        self.login()
        code = self.code('/api/email-change/request/', {'new_email': 'new@example.com'})
        stranger = create_user('stranger@example.com')
        self.client.force_authenticate(stranger)
        response = self.client.patch(
            '/api/users/me/',
            {
                'email': 'new@example.com',
                'code': code,
                'current_password': PASSWORD,
                'name': 'Novo nome',
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        stranger.refresh_from_db()
        self.assertEqual(stranger.email, 'stranger@example.com')
        self.assertEqual(stranger.name, 'Novo nome')
        self.assertFalse(EmailToken.objects.get(email='new@example.com').consumed)

    def test_generic_user_updates_ignore_credentials(self):
        self.client.force_authenticate(self.user)
        response = self.client.patch(
            '/api/users/me/',
            {'email': 'new@example.com', 'password': 'OutraSenha@456', 'name': 'Novo nome'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Novo nome')
        self.assertEqual(self.user.email, 'ana@example.com')
        self.assertTrue(self.user.check_password(PASSWORD))

        self.user.is_staff = True
        self.user.save(update_fields=['is_staff'])
        for method in (self.client.patch, self.client.put):
            response = method(
                f'/api/users/{self.user.pk}/',
                {'email': 'new@example.com', 'password': 'OutraSenha@456', 'name': 'Outro nome'},
                format='json',
            )
            self.assertEqual(response.status_code, 200, response.data)
            self.user.refresh_from_db()
            self.assertEqual(self.user.name, 'Outro nome')
            self.assertEqual(self.user.email, 'ana@example.com')
            self.assertTrue(self.user.check_password(PASSWORD))

    def test_failed_confirmation_attempts_are_persisted(self):
        code = self.code('/api/password-reset/request/', {'email': self.user.email})
        wrong = '111111' if code == '000000' else '000000'
        payload = {'email': self.user.email, 'code': wrong, 'new_password': 'OutraSenha@456'}
        for _ in range(5):
            self.assertEqual(self.client.post('/api/password-reset/confirm/', payload).status_code, 400)
        payload['code'] = code
        self.assertEqual(self.client.post('/api/password-reset/confirm/', payload).status_code, 400)
        self.assertEqual(EmailToken.objects.get(email=self.user.email).failed_attempts, 5)

    def test_legacy_mixed_case_email_can_log_in(self):
        self.user.email = 'Ana@Example.com'
        self.user.save(update_fields=['email'])
        response = self.client.post('/api/login/', {'email': 'ana@example.com', 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.data)

    def test_deactivation_prevents_login_and_refresh(self):
        self.login()
        self.assertEqual(self.client.post('/api/me/deactivate/').status_code, 200)
        self.assertEqual(
            self.client.post('/api/login/', {'email': self.user.email, 'password': PASSWORD}).status_code, 401
        )
        self.assertFalse(self.user.sessions.filter(is_active=True).exists())
