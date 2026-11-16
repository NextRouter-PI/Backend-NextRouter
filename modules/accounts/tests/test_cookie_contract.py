import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.hashers import make_password
from django.db import close_old_connections, connection, connections
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from modules.accounts.api.serializers.user import UserCreateSerializer
from modules.accounts.models import EmailToken, UserSession
from tests.helpers import PASSWORD, BaseAPITestCase, create_user, unique_cpf


class RegistrationCodeOrderTests(BaseAPITestCase):
    def test_wrong_signup_code_precedes_weak_password_and_does_not_consume(self):
        token = EmailToken.objects.create(email='signup@example.com', token_hash=make_password('123456'))
        serializer = UserCreateSerializer(
            data={
                'email': token.email,
                'name': 'Pessoa fictícia',
                'cpf': unique_cpf(),
                'code': '000000',
                'password': '123',
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)
        token.refresh_from_db()
        self.assertEqual(token.failed_attempts, 1)
        self.assertFalse(token.consumed)


class ProductionOriginTests(SimpleTestCase):
    def test_same_origin_does_not_depend_on_cors(self):
        env = {
            **os.environ,
            'SECRET_KEY': 'ficticia-sem-uso-em-producao-' * 3,
            'ALLOWED_HOSTS': 'app.example.com',
            'PUBLIC_ORIGIN': 'https://app.example.com',
            'CORS_ALLOWED_ORIGINS': '',
            'DATABASE_URL': 'postgresql://test:test@localhost/test',
            'REDIS_URL': 'redis://localhost:6379/15',
            'PRIVATE_DOCUMENT_ROOT': '/tmp/opencode/stage3-origin-documents',
            'OSRM_URL': 'https://routes.example.com',
            'GEOCODING_URL': 'https://geocode.example.com',
            'EMAIL_HOST': 'smtp.example.com',
            'EMAIL_HOST_USER': 'test',
            'EMAIL_HOST_PASSWORD': 'test',
        }
        code = (
            'from app.settings import prod as s; '
            'assert s.CORS_ALLOWED_ORIGINS == []; '
            'assert s.WS_ALLOWED_ORIGINS == [s.PUBLIC_ORIGIN]; '
            'assert s.CSRF_TRUSTED_ORIGINS == [s.PUBLIC_ORIGIN]; '
            'assert s.CSRF_COOKIE_SAMESITE == s.SESSION_COOKIE_SAMESITE == "Lax"'
        )
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        for origin in ('https://evil.example.com', 'http://app.example.com', 'https://app.example.com/path', '*'):
            with self.subTest(origin=origin):
                result = subprocess.run(
                    [sys.executable, '-c', code],
                    env={**env, 'PUBLIC_ORIGIN': origin},
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertNotEqual(result.returncode, 0)


@skipUnless(connection.vendor == 'postgresql', 'Refresh concorrente exige PostgreSQL.')
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RefreshConcurrencyTests(TransactionTestCase):
    def test_same_refresh_has_one_winner_without_revoking_winning_session(self):
        user = create_user('refresh-race@example.com')
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get('/api/csrf/').data['csrfToken']
        login = client.post('/api/login/', {'email': user.email, 'password': PASSWORD}, HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(login.status_code, 200)
        cookies = client.cookies.copy()
        barrier = Barrier(2)

        def refresh():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute('SELECT pg_backend_pid()')
                    pid = cursor.fetchone()[0]
                tab = APIClient(enforce_csrf_checks=True)
                tab.cookies = cookies.copy()
                barrier.wait(timeout=10)
                result = tab.post('/api/refresh/', HTTP_X_CSRFTOKEN=login.data['csrfToken'])
                return pid, result.status_code, tab.cookies, result.data
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(refresh) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(len({result[0] for result in results}), 2)
        self.assertEqual(sorted(result[1] for result in results), [200, 401])
        winner = next(result for result in results if result[1] == 200)
        self.assertNotIn('access', winner[3])
        client.cookies = winner[2]
        self.assertEqual(client.get('/api/users/me/').status_code, 200)
        self.assertEqual(UserSession.objects.filter(user=user, is_active=True).count(), 1)
