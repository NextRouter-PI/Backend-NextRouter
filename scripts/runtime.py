"""Entradas de produção por Procfile/Render/PDM com defaults seguros."""

import argparse
import os
import sys
from pathlib import Path


def required_integer(name, *, minimum=1, maximum=2147483647, default=None):
    value = os.environ.get(name, '').strip()
    if not value and default is not None:
        value = str(default)
    if not value.isascii() or not value.isdecimal() or not minimum <= int(value) <= maximum:
        raise ValueError('Parâmetro operacional ausente ou inválido.')
    return value


def optional_boolean(name, default='false'):
    value = os.environ.get(name, default).strip().lower()
    if value not in ('true', 'false'):
        raise ValueError('Parâmetro operacional booleano inválido.')
    return value == 'true'


def main():
    parser = argparse.ArgumentParser(description='Gerencia build e runtime validado de produção.')
    parser.add_argument('role', choices=('build', 'web', 'worker', 'release'))
    role = parser.parse_args().role
    os.environ['DJANGO_SETTINGS_MODULE'] = 'app.settings.prod'
    try:
        import django
        from django.conf import settings
        from django.core.management import call_command

        django.setup()
        Path(settings.PRIVATE_DOCUMENT_ROOT).mkdir(parents=True, exist_ok=True, mode=0o700)
        if role == 'build':
            call_command('collectstatic', interactive=False, verbosity=0)
            call_command('migrate', interactive=False)
            return
        if optional_boolean('AUTO_MIGRATE', default='false'):
            call_command('collectstatic', interactive=False, verbosity=0)
            call_command('migrate', interactive=False)
        call_command('check', deploy=True, fail_level='ERROR')
        require_frontend = role != 'worker' and optional_boolean('REQUIRE_FRONTEND_ARTIFACT', default='false')
        call_command('check_runtime', backend_only=not require_frontend)
        if role == 'release':
            return
        if role == 'web':
            command = [
                'daphne',
                '-b',
                '0.0.0.0',
                '-p',
                required_integer('PORT', maximum=65535, default=8000),
                '--access-log',
                os.devnull,
                '--verbosity',
                '0',
                'app.asgi:application',
            ]
        else:
            command = [sys.executable, 'manage.py', 'process_route_jobs']
            company_id_raw = os.environ.get('WORKER_COMPANY_ID', '').strip()
            all_companies_raw = os.environ.get('WORKER_ALL_COMPANIES', '').strip()
            all_companies = optional_boolean('WORKER_ALL_COMPANIES', default='false' if company_id_raw else 'true')
            if all_companies:
                if company_id_raw and all_companies_raw:
                    raise ValueError('Defina WORKER_ALL_COMPANIES=true ou WORKER_COMPANY_ID, não ambos.')
                command.append('--all-companies')
            else:
                command.extend(['--company-id', required_integer('WORKER_COMPANY_ID', minimum=1, maximum=2147483647)])
            for flag, name, minimum, maximum, default in (
                ('lease-seconds', 'WORKER_LEASE_SECONDS', 1, 2147483647, 60),
                ('max-attempts', 'WORKER_MAX_ATTEMPTS', 1, 2147483647, 3),
                ('retry-seconds', 'WORKER_RETRY_SECONDS', 0, 2147483647, 15),
                ('poll-seconds', 'WORKER_POLL_SECONDS', 1, 2147483647, 5),
                ('schedule-batch-size', 'WORKER_SCHEDULE_BATCH_SIZE', 1, 1000, 20),
                ('maintenance-batch-size', 'WORKER_MAINTENANCE_BATCH_SIZE', 1, 1000, 20),
                ('job-batch-size', 'WORKER_JOB_BATCH_SIZE', 1, 1000, 10),
            ):
                command.extend([f'--{flag}', required_integer(name, minimum=minimum, maximum=maximum, default=default)])
        sys.stdout.flush()
        sys.stderr.flush()
        os.execvp(command[0], command)
    except Exception:
        raise SystemExit(
            'Runtime recusado. Confira configuração, serviços, schema e artefato; nenhum migrate/seed foi executado.'
        ) from None


if __name__ == '__main__':
    main()
