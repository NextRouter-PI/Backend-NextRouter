import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.db import connection
from django.test import SimpleTestCase, TestCase

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


class RetirementGuardTests(SimpleTestCase):
    def test_existing_legacy_data_aborts_before_dropping_columns_or_records(self):
        for kind in ('profile', 'path'):
            with (
                self.subTest(kind=kind),
                tempfile.TemporaryDirectory(prefix='nextrouter-retirement-', dir='/tmp/opencode') as tmp,
            ):
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
                    'SECRET_KEY': 'chave-ficticia-exclusiva-do-teste-de-retirada',
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

                before = run('migrate', 'router', '0002_lost_item_audit', '--noinput')
                self.assertEqual(before.returncode, 0, before.stderr)
                fixture = """
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
apps = MigrationExecutor(connection).loader.project_state([('router', '0002_lost_item_audit')]).apps
user = apps.get_model('authenticator', 'User').objects.create(
    email='fixture@example.invalid', name='Fixture', cpf='90000000191', password='!'
)
company = apps.get_model('organizations', 'Company').objects.create(user=user, cnpj='90000001000191')
group = apps.get_model('organizations', 'CompanyRouteGroup').objects.create(
    company=company, name='Fixture', common_cep=''
)
"""
                if kind == 'profile':
                    fixture += """
apps.get_model('organizations', 'Passenger').objects.create(
    user=user, route_group=group, is_approved=True
)
"""
                else:
                    fixture += "apps.get_model('router', 'Path').objects.create(route_group=group, name='Fixture')"
                inserted = run('shell', '-c', fixture)
                self.assertEqual(inserted.returncode, 0, inserted.stderr)
                denied = run('migrate', '--noinput')
                self.assertNotEqual(denied.returncode, 0)
                self.assertIn('Remoção do legado bloqueada', denied.stderr)
                verify = """
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
assert not MigrationRecorder(connection).migration_qs.filter(app='organizations', name='0002_retire_legacy').exists()
assert not MigrationRecorder(connection).migration_qs.filter(app='router', name='0003_retire_legacy').exists()
with connection.cursor() as cursor:
    columns = {item.name for item in connection.introspection.get_table_description(cursor, 'authenticator_passenger')}
    assert 'route_group_id' in columns
    table = 'authenticator_passenger' if 'PROFILE' == 'profile' else 'router_path'
    cursor.execute('SELECT COUNT(*) FROM ' + table)
    assert cursor.fetchone()[0] == 1
""".replace('PROFILE', kind)
                preserved = run('shell', '-c', verify)
                self.assertEqual(preserved.returncode, 0, preserved.stderr)
