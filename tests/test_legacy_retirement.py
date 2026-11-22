import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.db import connection
from django.test import SimpleTestCase, TestCase, tag

from modules.organizations.models import CompanyRouteGroup, Driver, Passenger
from modules.transport.models import RouteOptimizationJob, Travel, Vehicle


class RetiredSchemaTests(TestCase):
    def test_obsolete_tables_and_columns_are_physically_absent(self):
        self.assertFalse(
            set(connection.introspection.table_names())
            & {
                'router_path',
                'router_company_route_schedule',
                'router_confirm_passenger_route',
            }
        )
        for model, obsolete in (
            (Passenger, {'route_group_id', 'is_approved', 'is_rejected'}),
            (Driver, {'route_group_id', 'is_approved', 'is_rejected'}),
            (CompanyRouteGroup, {'common_cep', 'reference_latitude', 'reference_longitude', 'geocoded_at'}),
            (Vehicle, {'route_group_id', 'driver_id', 'garage_cep'}),
            (Travel, {'path_id'}),
            (RouteOptimizationJob, {'path_id', 'passenger_ids', 'start', 'end'}),
        ):
            with self.subTest(model=model.__name__), connection.cursor() as cursor:
                columns = {
                    item.name for item in connection.introspection.get_table_description(cursor, model._meta.db_table)
                }
                self.assertFalse(columns & obsolete)

    def test_concrete_travel_fleet_and_job_fields_are_not_nullable_in_database(self):
        for model, required in (
            (Travel, {'service_day_id', 'service_id', 'planned_start', 'planned_end'}),
            (Vehicle, {'company_id', 'capacity'}),
            (RouteOptimizationJob, {'snapshot_id', 'input_revision'}),
        ):
            with self.subTest(model=model.__name__), connection.cursor() as cursor:
                columns = {
                    item.name: item
                    for item in connection.introspection.get_table_description(cursor, model._meta.db_table)
                }
                for name in required:
                    self.assertFalse(columns[name].null_ok, (model.__name__, name))


@tag('migration')
class CleanInitialMigrationTests(SimpleTestCase):
    def test_clean_database_migrates_from_initial_without_legacy_tables_or_pending_changes(self):
        with tempfile.TemporaryDirectory(prefix='nextrouter-initial-migration-') as tmp:
            env = {
                **os.environ,
                'DJANGO_SETTINGS_MODULE': 'app.settings.dev',
                'NEXTROUTER_ENV_FILE': f'{tmp}/empty.env',
                'DATABASE_URL': f'sqlite:///{tmp}/test.sqlite3',
                'MEDIA_ROOT': f'{tmp}/media',
                'PRIVATE_DOCUMENT_ROOT': f'{tmp}/documents',
                'NEXTROUTER_LAN_HOST': '',
                'FRONTEND_URL': 'http://127.0.0.1:5173',
                'REDIS_URL': '',
                'GEOCODING_URL': '',
                'OSRM_URL': '',
                'EMAIL_HOST': '',
                'CLOUDINARY_URL': '',
                'SECRET_KEY': 'chave-ficticia-exclusiva-do-teste-de-migrations',
            }

            def run(*args, env=env):
                return subprocess.run(
                    [sys.executable, 'manage.py', *args],
                    env=env,
                    cwd=Path(__file__).resolve().parents[1],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

            migrated = run('migrate', '--noinput')
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            checked = run('makemigrations', '--check', '--dry-run')
            self.assertEqual(checked.returncode, 0, checked.stderr)
            verify = """
from django.db import connection
tables = set(connection.introspection.table_names())
assert not (tables & {'router_path', 'router_company_route_schedule', 'router_confirm_passenger_route'})
assert {'authenticator_user', 'organizations_companymembership', 'router_travel'} <= tables
"""
            verified = run('shell', '-c', verify)
            self.assertEqual(verified.returncode, 0, verified.stderr)
