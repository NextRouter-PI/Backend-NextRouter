"""Entradas explícitas de produção por Procfile/PDM, sem migrate/seed implícitos."""

import argparse
import os
import sys


def required_integer(name, *, minimum=1, maximum=2147483647):
    value = os.environ.get(name, '')
    if not value.isascii() or not value.isdecimal() or not minimum <= int(value) <= maximum:
        raise ValueError('Parâmetro operacional ausente ou inválido.')
    return value


def optional_boolean(name, default='false'):
    value = os.environ.get(name, default).strip().lower()
    if value not in ('true', 'false'):
        raise ValueError('Parâmetro operacional booleano inválido.')
    return value == 'true'


def main():
    parser = argparse.ArgumentParser(description='Inicia runtime validado; migration é operação manual separada.')
    parser.add_argument('role', choices=('web', 'worker', 'release'))
    role = parser.parse_args().role
    os.environ['DJANGO_SETTINGS_MODULE'] = 'app.settings.prod'
    try:
        import django
        from django.core.management import call_command

        django.setup()
        call_command('check', deploy=True, fail_level='ERROR')
        call_command('check_runtime', backend_only=role == 'worker')
        if role == 'release':
            return
        if role == 'web':
            command = [
                'daphne',
                '-b',
                '0.0.0.0',
                '-p',
                required_integer('PORT', maximum=65535),
                '--access-log',
                os.devnull,
                '--verbosity',
                '0',
                'app.asgi:application',
            ]
        else:
            command = [sys.executable, 'manage.py', 'process_route_jobs']
            all_companies = optional_boolean('WORKER_ALL_COMPANIES', default='false')
            company_id_raw = os.environ.get('WORKER_COMPANY_ID', '').strip()
            if all_companies:
                if company_id_raw:
                    raise ValueError('Defina WORKER_ALL_COMPANIES=true ou WORKER_COMPANY_ID, não ambos.')
                command.append('--all-companies')
            else:
                command.extend(['--company-id', required_integer('WORKER_COMPANY_ID', minimum=1, maximum=2147483647)])
            for flag, name, minimum, maximum in (
                ('lease-seconds', 'WORKER_LEASE_SECONDS', 1, 2147483647),
                ('max-attempts', 'WORKER_MAX_ATTEMPTS', 1, 2147483647),
                ('retry-seconds', 'WORKER_RETRY_SECONDS', 0, 2147483647),
                ('poll-seconds', 'WORKER_POLL_SECONDS', 1, 2147483647),
                ('schedule-batch-size', 'WORKER_SCHEDULE_BATCH_SIZE', 1, 1000),
                ('maintenance-batch-size', 'WORKER_MAINTENANCE_BATCH_SIZE', 1, 1000),
                ('job-batch-size', 'WORKER_JOB_BATCH_SIZE', 1, 1000),
            ):
                command.extend([f'--{flag}', required_integer(name, minimum=minimum, maximum=maximum)])
        sys.stdout.flush()
        sys.stderr.flush()
        os.execvp(command[0], command)
    except Exception:
        raise SystemExit(
            'Runtime recusado. Confira configuração, serviços, schema e artefato; nenhum migrate/seed foi executado.'
        ) from None


if __name__ == '__main__':
    main()
