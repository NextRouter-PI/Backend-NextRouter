import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase, override_settings

from app.operational_logging import OperationalFormatter
from app.runtime_checks import check_dependencies, check_runtime, check_staticfiles
from modules.accounts.http import get_request_ip
from scripts.runtime import main, required_integer


class ProductionSettingsTests(SimpleTestCase):
    def settings_process(self, code, **extra):
        env = {
            **os.environ,
            'SECRET_KEY': 'ficticia-apenas-para-testes-' * 3,
            'ALLOWED_HOSTS': 'app.example.com',
            'PUBLIC_ORIGIN': 'https://app.example.com',
            'DATABASE_URL': 'postgresql://test:test@localhost/test',
            'REDIS_URL': 'redis://localhost:6379/15',
            'PRIVATE_DOCUMENT_ROOT': '',
            'OSRM_URL': 'https://routes.example.com',
            'GEOCODING_URL': 'https://geocode.example.com',
            'EMAIL_HOST': 'smtp.example.com',
            'EMAIL_HOST_USER': 'test',
            'EMAIL_HOST_PASSWORD': 'test',
            'TRUST_PROXY_HEADERS': 'false',
            'HSTS_SECONDS': '0',
            'HSTS_INCLUDE_SUBDOMAINS': 'false',
            'HSTS_PRELOAD': 'false',
            **extra,
        }
        return subprocess.run(
            [sys.executable, '-c', 'from app.settings import prod as s\n' + code],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_proxy_trust_hsts_and_asgi_connections_are_explicit_and_safe_by_default(self):
        result = self.settings_process("""
assert s.SECURE_PROXY_SSL_HEADER is None
assert s.SECURE_HSTS_SECONDS == 0
assert not s.SECURE_HSTS_INCLUDE_SUBDOMAINS and not s.SECURE_HSTS_PRELOAD
assert s.DATABASES['default']['CONN_MAX_AGE'] == 0
assert s.REST_FRAMEWORK['NUM_PROXIES'] == 0
assert s.IPWARE_HEADER_ORDER == ['REMOTE_ADDR']
assert s.FRONTEND_URL == s.FRONTEND_ADMIN_URL == s.PUBLIC_ORIGIN
assert s.CORS_ALLOWED_ORIGINS == []
assert s.WS_ALLOWED_ORIGINS == s.CSRF_TRUSTED_ORIGINS == [s.PUBLIC_ORIGIN]
assert s.CSRF_COOKIE_SAMESITE == s.SESSION_COOKIE_SAMESITE == 'Lax'
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.settings_process(
            """
assert s.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')
assert s.REST_FRAMEWORK['NUM_PROXIES'] == 1
assert s.IPWARE_PROXY_COUNT == 0
assert s.IPWARE_STRICT is False
assert s.IPWARE_HEADER_ORDER == ['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR']
assert s.DATABASES['default']['OPTIONS']['pool'] is True
assert s.SECURE_HSTS_SECONDS == 3600
assert not s.SECURE_HSTS_INCLUDE_SUBDOMAINS and not s.SECURE_HSTS_PRELOAD
""",
            TRUST_PROXY_HEADERS='true',
            HSTS_SECONDS='3600',
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_get_request_ip_ignores_spoofed_xff_behind_single_trusted_proxy(self):
        rf = RequestFactory()
        with override_settings(
            IPWARE_PROXY_COUNT=0,
            IPWARE_STRICT=False,
            IPWARE_HEADER_ORDER=['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'],
        ):
            honest = rf.get('/', HTTP_X_FORWARDED_FOR='203.0.113.5', REMOTE_ADDR='10.0.0.1')
            spoofed = rf.get('/', HTTP_X_FORWARDED_FOR='1.2.3.4, 203.0.113.5', REMOTE_ADDR='10.0.0.1')
            self.assertEqual(get_request_ip(honest), '203.0.113.5')
            self.assertEqual(get_request_ip(spoofed), '203.0.113.5')
        with override_settings(
            IPWARE_PROXY_COUNT=0,
            IPWARE_STRICT=True,
            IPWARE_HEADER_ORDER=['REMOTE_ADDR'],
        ):
            direct = rf.get('/', HTTP_X_FORWARDED_FOR='1.2.3.4', REMOTE_ADDR='198.51.100.7')
            self.assertEqual(get_request_ip(direct), '198.51.100.7')

    def test_invalid_origins_security_flags_public_storage_and_demo_services_are_rejected(self):
        for extra in (
            {'PUBLIC_ORIGIN': 'https://evil.example.com'},
            {'PUBLIC_ORIGIN': 'http://app.example.com'},
            {'PUBLIC_ORIGIN': 'https://app.example.com/path'},
            {'PUBLIC_ORIGIN': '*'},
            {'PUBLIC_ORIGIN': 'https://app.example.com:invalid'},
            {'PUBLIC_ORIGIN': 'https://@app.example.com'},
            {'TRUST_PROXY_HEADERS': 'yes'},
            {'HSTS_SECONDS': '-1'},
            {'HSTS_PRELOAD': 'true'},
            {'PRIVATE_DOCUMENT_ROOT': str(Path('frontend_dist/private').resolve())},
            {'PRIVATE_DOCUMENT_ROOT': 'relative-private'},
            {'OSRM_URL': 'https://ROUTER.PROJECT-OSRM.ORG'},
            {'OSRM_URL': 'https://router.project-osrm.org.'},
            {'GEOCODING_URL': 'https://nominatim.openstreetmap.org/search'},
            {'OSRM_URL': 'https://user:password@routes.example.com'},
            {'OSRM_URL': 'file:///tmp/test'},
            {'REDIS_URL': 'http://localhost'},
            {'REDIS_URL': 'redis://localhost:invalid'},
            {'SUPABASE_DATABASE_URL': 'sqlite:////tmp/invalido.sqlite3'},
            {'SUPABASE_DATABASE_URL': 'postgresql://localhost/postgres'},
        ):
            with self.subTest(extra=extra):
                self.assertNotEqual(self.settings_process('pass', **extra).returncode, 0)

    def test_supabase_database_url_enables_tls_and_pooler_compatibility_in_dev_and_prod(self):
        pooler_url = 'postgresql://postgres.projref:secret@aws-0-sa-east-1.pooler.supabase.com:6543/postgres'
        direct_url = 'postgresql://postgres:secret@db.projref.supabase.co:5432/postgres'

        prod_pooler = self.settings_process(
            """
db = s.DATABASES['default']
assert db['ENGINE'] == 'django.db.backends.postgresql'
assert db['HOST'] == 'aws-0-sa-east-1.pooler.supabase.com'
assert db['PORT'] == 6543
assert db['CONN_MAX_AGE'] == 0
assert db['CONN_HEALTH_CHECKS'] is True
assert db['DISABLE_SERVER_SIDE_CURSORS'] is True
assert db['OPTIONS']['sslmode'] == 'require'
assert 'pool' not in db['OPTIONS']
""",
            DATABASE_URL='',
            SUPABASE_DATABASE_URL=pooler_url,
        )
        self.assertEqual(prod_pooler.returncode, 0, prod_pooler.stderr)

        prod_direct = self.settings_process(
            """
db = s.DATABASES['default']
assert db['HOST'] == 'db.projref.supabase.co'
assert db['PORT'] == 5432
assert db.get('DISABLE_SERVER_SIDE_CURSORS') is not True
assert db['OPTIONS']['sslmode'] == 'require'
assert db['OPTIONS']['pool'] is True
""",
            DATABASE_URL=direct_url,
        )
        self.assertEqual(prod_direct.returncode, 0, prod_direct.stderr)

        dev_env = {
            **os.environ,
            'NEXTROUTER_ENV_FILE': '/tmp/nextrouter-env-inexistente',
            'SUPABASE_DATABASE_URL': pooler_url,
            'DATABASE_URL': '',
        }
        dev_result = subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    'from app.settings import dev as s\n'
                    "db = s.DATABASES['default']\n"
                    "assert db['ENGINE'] == 'django.db.backends.postgresql'\n"
                    "assert db['HOST'] == 'aws-0-sa-east-1.pooler.supabase.com'\n"
                    "assert db['DISABLE_SERVER_SIDE_CURSORS'] is True\n"
                    "assert db['OPTIONS']['sslmode'] == 'require'\n"
                ),
            ],
            env=dev_env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(dev_result.returncode, 0, dev_result.stderr)


class HealthTests(SimpleTestCase):
    def test_liveness_has_no_dependency_and_readiness_is_generic_uncached(self):
        self.assertEqual(self.client.get('/health/live/').json(), {'status': 'ok'})
        with patch('app.health.check_dependencies') as check:
            response = self.client.get('/health/ready/')
            check.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        with patch('app.health.check_dependencies', side_effect=DatabaseError('SenhaFicticiaNaoExpor')):
            response = self.client.get('/health/ready/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertNotIn(b'SenhaFicticiaNaoExpor', response.content)
        self.assertEqual(self.client.post('/health/live/').status_code, 405)
        self.assertEqual(self.client.get('/health/unknown', HTTP_ACCEPT='text/html').status_code, 404)

    def test_probes_check_database_cache_and_private_storage_without_business_queries(self):
        with (
            tempfile.TemporaryDirectory(prefix='nextrouter-probe-') as directory,
            override_settings(PRIVATE_DOCUMENT_ROOT=directory),
            patch('app.runtime_checks.connection') as connection,
            patch('app.runtime_checks.cache') as cache,
        ):
            connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
            cache.get.return_value = 'ok'
            check_dependencies()
            self.assertEqual(list(Path(directory).iterdir()), [])
            cache.get.return_value = 'wrong'
            with self.assertRaises(RuntimeError):
                check_dependencies()

    def test_runtime_refuses_pending_migrations_without_applying_them(self):
        with (
            override_settings(BACKEND_REVISION='a' * 40),
            patch('app.runtime_checks.check_dependencies'),
            patch('app.runtime_checks.MigrationExecutor') as executor,
            patch('app.runtime_checks.check_staticfiles') as staticfiles,
            patch('app.runtime_checks.verify_artifact') as verify,
        ):
            executor.return_value.migration_plan.return_value = [object()]
            with self.assertRaises(RuntimeError):
                check_runtime()
            verify.assert_not_called()
            staticfiles.assert_not_called()
            executor.return_value.migration_plan.return_value = []
            check_runtime()
            staticfiles.assert_called_once()
            verify.assert_called_once()
            verify.reset_mock()
            check_runtime(require_frontend=False)
            self.assertEqual(staticfiles.call_count, 2)
            verify.assert_not_called()
        with (
            patch(
                'modules.transport.management.commands.check_runtime.check_runtime',
                side_effect=RuntimeError('NuncaExporErroPrivado'),
            ),
            self.assertRaises(CommandError) as caught,
        ):
            call_command('check_runtime')
        self.assertNotIn('NuncaExporErroPrivado', str(caught.exception))

    def test_staticfiles_manifest_must_exist_be_valid_and_readable_before_exec(self):
        with tempfile.TemporaryDirectory(prefix='nextrouter-statics-') as directory:
            manifest = Path(directory) / 'staticfiles.json'
            storage_settings = {
                'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
            }
            with (
                override_settings(STATIC_ROOT=directory, STORAGES=storage_settings),
                self.assertRaises(FileNotFoundError),
            ):
                check_staticfiles()
            manifest.write_text('{invalid')
            with (
                override_settings(STATIC_ROOT=directory, STORAGES=storage_settings),
                self.assertRaises(ValueError),
            ):
                check_staticfiles()
            manifest.write_text(json.dumps({'version': '1.1', 'hash': 'fixture', 'paths': {}}))
            with override_settings(STATIC_ROOT=directory, STORAGES=storage_settings):
                check_staticfiles()
            with (
                patch('app.runtime_checks.storages') as storages,
                self.assertRaises(PermissionError),
            ):
                storages.__getitem__.return_value.open.side_effect = PermissionError('FicticioNaoExpor')
                check_staticfiles()


class OperationalLoggingTests(SimpleTestCase):
    def test_arbitrary_messages_requests_headers_and_exceptions_never_enter_output(self):
        marker = 'NaoRegistrarSegredoFicticio'
        record = logging.LogRecord('django.request', logging.ERROR, __file__, 1, marker + '%s', (marker,), None)
        record.request = MagicMock()
        record.request.META = {'HTTP_COOKIE': marker, 'HTTP_AUTHORIZATION': marker}
        record.exc_info = (ValueError, ValueError(marker), None)
        record.status_code = 500
        output = OperationalFormatter().format(record)
        self.assertNotIn(marker, output)
        self.assertEqual(json.loads(output)['status'], 500)

    def test_worker_metrics_are_counts_and_duration_only(self):
        record = logging.LogRecord(
            'worker',
            logging.INFO,
            __file__,
            1,
            'worker_cycle schedules=%d days=%d jobs=%d duration_ms=%d',
            (1, 2, 3, 12.3),
            None,
        )
        output = json.loads(OperationalFormatter().format(record))
        self.assertEqual(output['event'], 'worker_cycle')
        self.assertEqual(output['duration_ms'], 12)
        self.assertEqual(output['jobs'], 3)
        self.assertNotIn('message', output)


class RuntimeEntryTests(SimpleTestCase):
    def test_environment_numbers_are_not_shell_code_or_implicit_defaults(self):
        for value in ('', '1; echo x', '-1', '0', '\uff11'):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {'TEST_LIMIT': value}),
                self.assertRaises(ValueError),
            ):
                required_integer('TEST_LIMIT')

    def test_web_and_release_validate_before_exec_and_never_migrate_or_seed(self):
        for role in ('web', 'release'):
            with (
                self.subTest(role=role),
                patch.object(sys, 'argv', ['runtime', role]),
                patch.dict(os.environ, {'PORT': '8000'}),
                patch('django.setup'),
                patch('django.core.management.call_command') as command,
                patch('os.execvp') as execute,
            ):
                main()
                self.assertEqual([call.args[0] for call in command.call_args_list], ['check', 'check_runtime'])
                self.assertEqual(execute.call_count, int(role == 'web'))
                if role == 'web':
                    self.assertIn('--access-log', execute.call_args.args[1])
        with (
            patch.object(sys, 'argv', ['runtime', 'build']),
            patch('django.setup'),
            patch('django.core.management.call_command') as command,
            patch('os.execvp') as execute,
        ):
            main()
            self.assertEqual([call.args[0] for call in command.call_args_list], ['collectstatic', 'migrate'])
            execute.assert_not_called()
        with (
            patch.object(sys, 'argv', ['runtime', 'worker']),
            patch.dict(os.environ, {}, clear=True),
            patch('django.setup'),
            patch('django.core.management.call_command'),
            patch('os.execvp') as execute,
        ):
            # Sem variáveis WORKER_*, usa defaults seguros e --all-companies
            main()
            self.assertIn('--all-companies', execute.call_args.args[1])
            execute.reset_mock()
            os.environ['WORKER_COMPANY_ID'] = '1'
            main()
            self.assertIn('--company-id', execute.call_args.args[1])
            execute.reset_mock()
            os.environ['WORKER_ALL_COMPANIES'] = 'true'
            with self.assertRaises(SystemExit):
                main()
            execute.assert_not_called()
