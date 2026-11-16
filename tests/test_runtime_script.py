import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts.test_runtime import Smoke, checked, local_socket


class RuntimeScriptIsolationTests(SimpleTestCase):
    def test_remote_context_is_rejected_before_daemon_or_resources(self):
        with (
            patch.dict(os.environ, {'DOCKER_CONTEXT': 'remote', 'DOCKER_HOST': 'unix:///ignored.sock'}),
            patch('scripts.test_runtime.checked', return_value='ssh://remote.invalid\n') as command,
            self.assertRaises(RuntimeError),
        ):
            local_socket()
        command.assert_called_once()
        self.assertEqual(command.call_args.args[0][:3], ['docker', 'context', 'inspect'])

    def test_explicit_context_precedes_inherited_docker_host(self):
        with (
            patch.dict(os.environ, {'DOCKER_CONTEXT': 'local', 'DOCKER_HOST': 'tcp://remote.invalid'}),
            patch('scripts.test_runtime.checked', side_effect=['unix:///local.sock\n', 'ok']) as command,
        ):
            self.assertEqual(local_socket(), '/local.sock')
        self.assertEqual(command.call_args_list[-1].args[0], ['docker', 'info'])

    def test_command_failure_does_not_reflect_args_stdout_or_stderr(self):
        marker = 'SegredoFicticioNaoRegistrar'
        result = subprocess.CompletedProcess(['fake'], 1, stdout=marker, stderr=marker)
        with (
            patch('scripts.test_runtime.subprocess.run', return_value=result),
            self.assertRaises(RuntimeError) as caught,
        ):
            checked(['fake', marker])
        self.assertNotIn(marker, str(caught.exception))

    def test_compose_uses_only_explicit_temporary_context_env_and_project(self):
        with tempfile.TemporaryDirectory(prefix='nextrouter-script-', dir='/tmp/opencode') as temporary:
            smoke = Smoke(temporary, '/local.sock')
            with patch('scripts.test_runtime.checked', return_value='ok') as command:
                smoke.compose('config', '--quiet')
                args = command.call_args.args[0]
            self.assertIn(str(Path(temporary) / 'context/smoke.env'), args)
            self.assertIn(smoke.project, args)
            self.assertEqual(smoke.context.parent, Path(temporary))
            with patch.object(smoke, 'compose') as compose, patch('scripts.test_runtime.checked', return_value=''):
                smoke.cleanup()
                compose.assert_not_called()
                smoke.owned = True
                with patch('scripts.test_runtime.subprocess.run') as run:
                    smoke.cleanup()
                compose.assert_called_once_with('down', '--volumes', '--remove-orphans', timeout=180)
                self.assertEqual(run.call_args.args[0][-1], f'nextrouter:{smoke.revision}')
