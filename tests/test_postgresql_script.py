"""Valida isolamento/limpeza do roteiro sem iniciar Docker ou conectar em banco."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.test import SimpleTestCase

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'test_postgresql.sh'
STUB = """import json, os, sys
from pathlib import Path
name, args = Path(sys.argv[0]).name, sys.argv[1:]
with open(os.environ['SCRIPT_TEST_LOG'], 'a') as log:
    log.write(json.dumps({
        'name': name, 'args': args,
        'database': os.environ.get('DATABASE_URL'),
        'documents': os.environ.get('PRIVATE_DOCUMENT_ROOT'),
        'external': [os.environ.get(key) for key in
                     ('REDIS_URL', 'GEOCODING_URL', 'OSRM_URL', 'EMAIL_HOST', 'CLOUDINARY_URL')],
    }) + '\\n')
if name == 'docker':
    if args[0] == 'context':
        print(os.environ.get('SCRIPT_TEST_CONTEXT_HOST', 'unix:///test-only.sock'))
    if args[0] == 'info' and os.environ.get('SCRIPT_TEST_NO_DOCKER'):
        sys.exit(1)
    if args[0] == 'run':
        print('new-test-container')
    if args[0] == 'port':
        print('127.0.0.1:65432')
if name == 'pdm' and args[:2] == ['run', 'test']:
    sys.exit(int(os.environ.get('SCRIPT_TEST_RESULT', '0')))
"""


@skipUnless(os.name == 'posix' and shutil.which('bash'), 'O roteiro Docker exige Bash em ambiente Unix.')
class PostgreSQLScriptTests(SimpleTestCase):
    def setUp(self):
        Path('/tmp/opencode').mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir='/tmp/opencode', prefix='postgresql-script-test-')
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.log = self.directory / 'calls.jsonl'
        for name in ('docker', 'pdm'):
            executable = self.directory / name
            executable.write_text(f'#!{sys.executable}\n{STUB}')
            executable.chmod(0o700)

    def run_script(self, **extra):
        env = {
            **os.environ,
            'PATH': f'{self.directory}{os.pathsep}{os.environ["PATH"]}',
            'DOCKER_HOST': 'unix:///test-only.sock',
            'DOCKER_CONTEXT': '',
            'DATABASE_URL': 'postgresql://unrelated-do-not-use/other_database',
            'SCRIPT_TEST_LOG': str(self.log),
            **extra,
        }
        result = subprocess.run(
            ['bash', str(SCRIPT), 'modules.transport.tests.test_service_concurrency'],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def test_success_uses_only_new_container_database_and_cleans_up(self):
        result, calls = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        run = next(call for call in calls if call['name'] == 'docker' and call['args'][0] == 'run')['args']
        self.assertEqual(run[run.index('--publish') + 1], '127.0.0.1::5432')
        self.assertIn('--tmpfs', run)
        self.assertNotIn('--volume', run)
        pdm_calls = [call for call in calls if call['name'] == 'pdm']
        self.assertEqual(len(pdm_calls), 3)
        for call in pdm_calls:
            self.assertEqual(
                call['database'],
                'postgresql://nextrouter_test:local_test_only@127.0.0.1:65432/nextrouter_stage2',
            )
            self.assertEqual(call['external'], [''] * 5)
            self.assertFalse(Path(call['documents']).parent.exists())
        self.assertEqual(calls[-1]['args'], ['rm', '--force', 'new-test-container'])

    def test_failed_suite_preserves_failure_status_and_removes_own_container(self):
        result, calls = self.run_script(SCRIPT_TEST_RESULT='7')
        self.assertEqual(result.returncode, 7)
        self.assertEqual(calls[-1]['args'], ['rm', '--force', 'new-test-container'])

    def test_unavailable_docker_stops_before_creating_resources(self):
        result, calls = self.run_script(SCRIPT_TEST_NO_DOCKER='1')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Docker indisponível', result.stderr)
        self.assertEqual([(call['name'], call['args']) for call in calls], [('docker', ['info'])])

    def test_remote_context_is_rejected_without_running_commands(self):
        result, calls = self.run_script(DOCKER_HOST='tcp://remote-example.invalid:2375')
        self.assertEqual(result.returncode, 1)
        self.assertIn('não um contexto remoto', result.stderr)
        self.assertEqual(calls, [])
        # DOCKER_CONTEXT tem precedência sobre DOCKER_HOST no CLI.
        result, calls = self.run_script(
            DOCKER_CONTEXT='remote-test', SCRIPT_TEST_CONTEXT_HOST='ssh://remote-example.invalid'
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn('não um contexto remoto', result.stderr)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['args'][0], 'context')
