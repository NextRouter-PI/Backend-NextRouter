import io
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from modules.organizations.models import Company, CompanyMembership
from modules.transport.models import RecurringService, ServiceDay, Travel


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'], DEBUG=True)
class DatedSeedTests(TestCase):
    def test_seed_requires_explicit_confirmation_and_never_runs_in_production(self):
        for command in ('seed_demo_data', 'seed_data'):
            with self.assertRaises(CommandError):
                call_command(command)
        with (
            override_settings(DEBUG=False),
            patch.dict('os.environ', {'DEMO_PASSWORD': 'senha-apenas-fixture'}),
            self.assertRaises(CommandError),
        ):
            call_command('seed_demo_data', confirm_fictitious=True)
        self.assertFalse(Company.objects.exists())
        with self.assertRaises(CommandError):
            call_command('backfill_user_data')

    def test_seed_builds_new_domain_idempotently_without_logging_password(self):
        output = io.StringIO()
        with patch.dict('os.environ', {'DEMO_PASSWORD': 'senha-apenas-fixture'}):
            for _ in range(2):
                call_command('seed_demo_data', confirm_fictitious=True, stdout=output)
        self.assertEqual(Company.objects.count(), 1)
        self.assertEqual(CompanyMembership.objects.filter(status='active').count(), 2)
        self.assertEqual(RecurringService.objects.count(), 2)
        self.assertEqual(ServiceDay.objects.count(), 1)
        self.assertEqual(Travel.objects.count(), 2)
        self.assertNotIn('senha-apenas-fixture', output.getvalue())
