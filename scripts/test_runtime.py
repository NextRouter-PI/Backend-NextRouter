"""Smoke real local: imagem, Compose isolado, TLS/WSS e restore de dados só fictícios."""

import argparse
import base64
import hashlib
import http.cookiejar
import json
import os
import re
import shutil
import signal
import socket
import ssl
import struct
import subprocess
import tempfile
import time
import traceback
from datetime import UTC, datetime
from math import isclose
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, HTTPSHandler, Request, build_opener
from uuid import uuid4

from shared.frontend_artifact import prepare_artifact

CLI_IMAGE = 'docker:29-cli@sha256:5a7af0dcb0e46c803efe9b45371dd21cb500e5b4453250394ac6f06d49b6e6f1'


class ExternalCommandError(RuntimeError):
    def __init__(self, reason):
        super().__init__('Comando externo recusado; argumentos e saída omitidos.')
        self.reason = reason


def checked(command, *, data=None, timeout=180, binary=False):
    result = subprocess.run(command, input=data, capture_output=True, text=not binary, timeout=timeout)
    if result.returncode:
        # Comandos podem carregar credenciais em env/headers; não refletir argv/stdout/stderr.
        stderr = result.stderr.decode(errors='replace') if binary else result.stderr
        reason = 'command_failed'
        for name in (
            'PermissionError',
            'IntegrityError',
            'ImproperlyConfigured',
            'FieldError',
            'OperationalError',
            'ModuleNotFoundError',
            'ValidationError',
            'ZoneInfoNotFoundError',
            'ValueError',
        ):
            if re.search(r'^' + name + ':', stderr, re.MULTILINE):
                reason = name
                break
        raise ExternalCommandError(reason)
    return result.stdout


def local_socket():
    context = os.environ.get('DOCKER_CONTEXT')
    host = checked(
        ['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}', context]
        if context
        else ['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}']
    ).strip()
    if not context:
        host = os.environ.get('DOCKER_HOST') or host
    if not host.startswith('unix://'):
        raise RuntimeError('Use daemon Docker local por socket Unix; contexto remoto recusado.')
    checked(['docker', 'info'])
    return host.removeprefix('unix://')


class WebSocket:
    def __init__(self, *, port, tls, origin, path, cookies=''):
        self.socket = tls.wrap_socket(
            socket.create_connection(('127.0.0.1', port), timeout=10), server_hostname='localhost'
        )
        self.buffer = b''
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f'GET {path} HTTP/1.1\r\nHost: localhost:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: {origin}\r\nCookie: {cookies}\r\n\r\n'
        )
        self.socket.sendall(request.encode())
        while b'\r\n\r\n' not in self.buffer:
            chunk = self.socket.recv(4096)
            if not chunk:
                raise RuntimeError('Handshake WSS encerrado sem resposta.')
            self.buffer += chunk
        header, self.buffer = self.buffer.split(b'\r\n\r\n', 1)
        self.connected = header.startswith(b'HTTP/1.1 101')
        if self.connected:
            accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
            assert accept in header

    def read(self, size):
        while len(self.buffer) < size:
            chunk = self.socket.recv(4096)
            if not chunk:
                raise RuntimeError('WSS fechou antes do evento esperado.')
            self.buffer += chunk
        value, self.buffer = self.buffer[:size], self.buffer[size:]
        return value

    def send(self, payload, opcode=1):
        mask = os.urandom(4)
        body = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        header = (
            bytes([0x80 | opcode, 0x80 | len(body)])
            if len(body) < 126
            else bytes([0x80 | opcode, 0xFE]) + struct.pack('!H', len(body))
        )
        self.socket.sendall(header + mask + body)

    def receive(self):
        first, second = self.read(2)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack('!H', self.read(2))[0]
        elif length == 127:
            length = struct.unpack('!Q', self.read(8))[0]
        if length > 65536 or second & 0x80:
            raise RuntimeError('Frame inesperado no smoke.')
        payload = self.read(length)
        opcode = first & 0x0F
        if opcode == 9:
            self.send(payload, opcode=10)
            return self.receive()
        return ('closed', struct.unpack('!H', payload[:2])[0]) if opcode == 8 else ('json', json.loads(payload))

    def close(self):
        self.socket.close()


class Smoke:
    def __init__(self, root, socket_path):
        self.root = Path(root)
        self.socket_path = socket_path
        self.project = 'nextrouter-smoke-' + uuid4().hex[:12]
        self.revision = uuid4().hex + uuid4().hex[:8]  # Identidade SOMENTE fictícia, não um commit real.
        self.context = self.root / 'context'
        self.context.mkdir()
        self.envfile = self.context / 'smoke.env'
        self.owned = False
        self.cli_started = False
        self.restore_volume = self.project + '_restored_documents'
        self.created_restore_volume = False
        self.phase = 'preparation'

    def compose(self, *args, data=None, binary=False, timeout=180):
        command = [
            'docker',
            'run',
            '--rm',
            '-i',
            '--label',
            f'nextrouter.runtime-cli={self.project}',
            '--mount',
            f'type=bind,src={self.socket_path},dst=/var/run/docker.sock',
            '--mount',
            f'type=bind,src={self.root},dst={self.root}',
            '--workdir',
            str(self.context),
            '--env',
            'DOCKER_HOST=unix:///var/run/docker.sock',
            CLI_IMAGE,
            'docker',
            'compose',
            '--project-name',
            self.project,
            '--env-file',
            str(self.envfile),
            '-f',
            'compose.yaml',
            '-f',
            'compose.smoke.yaml',
            *args,
        ]
        self.cli_started = True
        return checked(command, data=data, binary=binary, timeout=timeout)

    def prepare(self):
        for command in (['ps', '-aq'], ['volume', 'ls', '-q'], ['network', 'ls', '-q']):
            existing = checked([
                'docker',
                *command,
                '--filter',
                f'label=com.docker.compose.project={self.project}',
            ]).strip()
            if existing:
                raise RuntimeError('Projeto aleatório já existe; recursos existentes não serão usados/removidos.')
        image = subprocess.run(['docker', 'image', 'inspect', f'nextrouter:{self.revision}'], capture_output=True)
        if image.returncode == 0:
            raise RuntimeError('Imagem de teste já existe; não será substituída.')
        repository = Path(__file__).resolve().parents[1]
        for name in ('app', 'modules', 'shared', 'static', 'scripts', 'deploy'):
            shutil.copytree(
                repository / name, self.context / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'tls')
            )
        for name in ('Dockerfile', '.dockerignore', 'pyproject.toml', 'pdm.lock', 'manage.py', 'compose.yaml'):
            shutil.copyfile(repository / name, self.context / name)
        source = self.root / 'fixture-dist'
        (source / 'assets').mkdir(parents=True)
        (source / 'index.html').write_text(
            '<!doctype html><div>fixture-only-not-vue</div>'
            '<script type="module" src="/assets/index-Fixture.js"></script>'
        )
        (source / 'assets/index-Fixture.js').write_text('/* fixture, não build Vue */')
        prepare_artifact(
            source=source,
            destination=self.root / 'prepared',
            frontend_revision='a' * 40,
            backend_revision=self.revision,
        )
        shutil.copytree(self.root / 'prepared/frontend_dist', self.context / 'frontend_dist')
        shutil.copyfile(self.root / 'prepared/frontend-release.json', self.context / 'frontend-release.json')
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            self.port = reservation.getsockname()[1]
        tls = self.context / 'tls'
        tls.mkdir()
        checked([
            'openssl',
            'req',
            '-x509',
            '-newkey',
            'rsa:2048',
            '-nodes',
            '-keyout',
            str(tls / 'key.pem'),
            '-out',
            str(tls / 'cert.pem'),
            '-days',
            '1',
            '-subj',
            '/CN=localhost',
            '-addext',
            'subjectAltName=DNS:localhost,IP:127.0.0.1',
        ])
        (tls / 'key.pem').chmod(0o600)
        self.tls = ssl.create_default_context(cafile=str(tls / 'cert.pem'))
        self.origin = f'https://localhost:{self.port}'
        self.database = 'nextrouter_smoke_' + uuid4().hex[:12]
        values = {
            'BACKEND_REVISION': self.revision,
            'SECRET_KEY': 'ficticia-sem-uso-fora-do-smoke-' * 3,
            'ALLOWED_HOSTS': 'localhost',
            'PUBLIC_ORIGIN': self.origin,
            'HSTS_SECONDS': '3600',
            'DATABASE_URL': f'postgresql://smoke:local_test_only@db:5432/{self.database}',
            'POSTGRES_DB': self.database,
            'POSTGRES_USER': 'smoke',
            'POSTGRES_PASSWORD': 'local_test_only',
            'OSRM_URL': 'https://routes.example.invalid',
            'GEOCODING_URL': 'https://geocode.example.invalid',
            'EMAIL_HOST': 'smtp.example.invalid',
            'EMAIL_HOST_USER': 'fixture',
            'EMAIL_HOST_PASSWORD': 'fixture',
            'DEFAULT_FROM_EMAIL': 'fixture@example.invalid',
            'HTTPS_PORT': str(self.port),
            'TLS_DIRECTORY': str(tls),
            'WORKER_COMPANY_ID': '1',
            'WORKER_LEASE_SECONDS': '60',
            'WORKER_MAX_ATTEMPTS': '3',
            'WORKER_RETRY_SECONDS': '5',
            'WORKER_POLL_SECONDS': '2',
            'WORKER_SCHEDULE_BATCH_SIZE': '1',
            'WORKER_MAINTENANCE_BATCH_SIZE': '2',
            'WORKER_JOB_BATCH_SIZE': '1',
        }
        self.envfile.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
        self.envfile.chmod(0o600)
        (self.context / 'compose.smoke.yaml').write_text(
            'services:\n  web:\n    healthcheck:\n      interval: 1s\n      start_period: 20s\n'
            '  worker:\n    restart: "no"\n    environment:\n      NEXTROUTER_RUNTIME_SMOKE: "1"\n'
        )
        self.compose('config', '--quiet')
        self.owned = True

    def python(self, code, *, restored=False):
        extra = []
        if restored:
            extra = [
                '--env',
                f'DATABASE_URL=postgresql://smoke:local_test_only@db:5432/{self.database}_restored',
                '--volume',
                f'{self.restore_volume}:/srv/private-documents',
            ]
        return self.compose(
            'run', '--rm', '--no-deps', '-T', *extra, 'web', 'python', '-c', 'import django; django.setup(); ' + code
        ).strip()

    def wait(self, predicate, *, seconds=90):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.5)
        raise RuntimeError('Tempo de prontidão excedido.')

    def request(self, opener, path, *, data=None, csrf=None, method=None, extra_headers=None):
        headers = {'Origin': self.origin, **(extra_headers or {})}
        if data is not None:
            data = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        if csrf:
            headers['X-CSRFToken'] = csrf
        request = Request(self.origin + path, data=data, headers=headers, method=method)
        try:
            response = opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    def client(self):
        cookies = http.cookiejar.CookieJar()
        return build_opener(HTTPSHandler(context=self.tls), HTTPCookieProcessor(cookies)), cookies

    def login(self, role):
        opener, cookies = self.client()
        code, _, body = self.request(opener, '/api/csrf/')
        assert code == 200
        csrf = json.loads(body)['csrfToken']
        credentials = {'email': f'{role}@example.invalid', 'password': 'SenhaFicticiaExclusivaDoSmoke!42'}
        assert self.request(opener, '/api/login/', data=credentials)[0] == 403
        code, headers, body = self.request(
            opener,
            '/api/login/',
            data=credentials,
            csrf=csrf,
            extra_headers={'X-Forwarded-For': '198.51.100.77', 'X-Forwarded-Proto': 'http'},
        )
        assert code == 200 and not {'access', 'refresh'} & json.loads(body).keys()
        for cookie in headers.get_all('Set-Cookie'):
            if cookie.startswith(('access_token=', 'refresh_token=')):
                assert all(value in cookie for value in ('HttpOnly', 'Secure', 'SameSite=Lax', 'Path=/'))
                assert 'Domain=' not in cookie
        return opener, cookies, json.loads(body)['csrfToken']

    def run(self):
        self.prepare()
        self.phase = 'image_build'
        self.compose('build', 'web', timeout=900)
        self.phase = 'dependency_startup'
        self.compose('up', '-d', '--wait', 'db', 'redis')
        self.phase = 'clean_migration'
        self.compose('run', '--rm', '--no-deps', '-T', 'web', 'python', 'manage.py', 'migrate', '--noinput')
        self.phase = 'fictitious_fixture'
        fixture = Path(__file__).with_name('runtime_fixture.py').read_text()
        raw = self.compose(
            'run', '--rm', '--no-deps', '-T', '--env', 'NEXTROUTER_RUNTIME_SMOKE=1', 'web', 'python', '-', data=fixture
        )
        self.fixture = json.loads(raw)
        self.phase = 'release_check'
        self.compose('run', '--rm', '--no-deps', '-T', 'web', 'python', '-m', 'scripts.runtime', 'release')
        print('Imagem, configuração Compose, instalação limpa e release-check: OK.', flush=True)
        self.phase = 'worker_recovery'
        self.compose('up', '-d', 'worker')
        partial = (
            'from modules.transport.models import AutomationSchedule; '
            'print(AutomationSchedule.objects.get().cursor_date is not None)'
        )
        self.wait(lambda: self.python(partial) == 'True')
        self.compose('kill', '--signal', 'SIGKILL', 'worker')
        self.compose('up', '-d', 'worker')
        completed = (
            'from modules.transport.models import AutomationSchedule; '
            'print(AutomationSchedule.objects.get().last_completed_at is not None)'
        )
        self.wait(lambda: self.python(completed) == 'True')
        self.compose('stop', 'worker')
        worker_id = self.compose('ps', '-aq', 'worker').strip()
        assert checked(['docker', 'inspect', '--format', '{{.State.ExitCode}}', worker_id]).strip() == '0'
        assert self.python('from modules.transport.models import ServiceDay; print(ServiceDay.objects.count())') == '5'
        print('Worker: SIGKILL/retomada sem duplicar e SIGTERM limpo: OK.', flush=True)
        self.phase = 'https'
        self.compose('up', '-d', '--wait', 'web', 'proxy', timeout=180)
        client, _ = self.client()
        code, headers, body = self.request(client, '/', extra_headers={'Accept': 'text/html'})
        assert code == 200 and b'fixture-only-not-vue' in body
        assert headers['Strict-Transport-Security'] == 'max-age=3600'
        assert self.request(client, '/deep/link', method='HEAD', extra_headers={'Accept': 'text/html'})[0] == 200
        for path in (
            '/api/missing/',
            '/assets/missing.js',
            '/frontend-release.json',
            '/html-template-test/',
            '/media/' + self.fixture['document_name'],
        ):
            assert self.request(client, path, extra_headers={'Accept': 'text/html'})[0] == 404
        assert self.request(client, '/static/admin/css/base.css')[0] == 200
        assert self.request(client, '/assets/index-Fixture.js')[0] == 200
        passenger, passenger_cookies, csrf = self.login('passenger')
        driver, driver_cookies, _ = self.login('driver')
        assert self.request(passenger, self.fixture['document_url'])[0] == 404
        assert self.request(driver, self.fixture['document_url'])[0] == 200
        assert self.request(passenger, '/api/users/me/')[0] == 200
        code, _, body = self.request(passenger, '/api/refresh/', data={}, csrf=csrf)
        assert code == 200 and not {'access', 'refresh'} & json.loads(body).keys()
        self.phase = 'wss'
        path = f'/ws/travels/{self.fixture["travel_id"]}/location/'

        def cookie(jar):
            return '; '.join(f'{item.name}={item.value}' for item in jar)

        foreign = WebSocket(
            port=self.port, tls=self.tls, origin='https://invalid.example', path=path, cookies=cookie(passenger_cookies)
        )
        assert not foreign.connected
        foreign.close()
        anonymous = WebSocket(port=self.port, tls=self.tls, origin=self.origin, path=path)
        assert not anonymous.connected
        anonymous.close()
        listener = WebSocket(
            port=self.port, tls=self.tls, origin=self.origin, path=path, cookies=cookie(passenger_cookies)
        )
        sender = WebSocket(port=self.port, tls=self.tls, origin=self.origin, path=path, cookies=cookie(driver_cookies))
        try:
            assert listener.connected and sender.connected
            assert listener.receive()[0] == sender.receive()[0] == 'json'
            sender.send(
                json.dumps({
                    'latitude': -26.35,
                    'longitude': -48.8,
                    'recorded_at': datetime.now(UTC).isoformat(),
                }).encode()
            )
            kind, position = listener.receive()
            assert kind == 'json' and isclose(position['position']['latitude'], -26.35) and not position['stale']
            assert self.request(passenger, '/api/me/logout/', data={}, csrf=csrf)[0] == 200
            assert listener.receive() == ('closed', 4001)
            assert self.request(passenger, '/api/users/me/')[0] == 401
        finally:
            listener.close()
            sender.close()
        print(
            'HTTPS/WSS, cookies/CSRF/refresh/logout, Origin, assets e download privado: OK (sem navegador).', flush=True
        )
        self.phase = 'dependency_recovery'
        self.compose('stop', 'redis')
        code, _, body = self.request(client, '/health/ready/')
        assert code == 503 and json.loads(body) == {'status': 'unavailable'}
        self.compose('start', 'redis')
        self.wait(lambda: self.request(client, '/health/ready/')[0] == 200)
        self.compose('restart', 'db')
        self.wait(lambda: self.request(client, '/health/ready/')[0] == 200)
        self.phase = 'backup_restore'
        backup = self.compose('exec', '-T', 'db', 'pg_dump', '-U', 'smoke', '-Fc', self.database, binary=True)
        self.compose('exec', '-T', 'db', 'createdb', '-U', 'smoke', self.database + '_restored')
        self.compose(
            'exec',
            '-T',
            'db',
            'pg_restore',
            '-U',
            'smoke',
            '--no-owner',
            '-d',
            self.database + '_restored',
            data=backup,
            binary=True,
        )
        documents = self.compose(
            'run', '--rm', '--no-deps', '-T', 'web', 'tar', '-C', '/srv/private-documents', '-cf', '-', '.', binary=True
        )
        checked([
            'docker',
            'volume',
            'create',
            '--label',
            f'com.docker.compose.project={self.project}',
            self.restore_volume,
        ])
        self.created_restore_volume = True
        self.compose(
            'run',
            '--rm',
            '--no-deps',
            '-T',
            '--volume',
            self.restore_volume + ':/srv/private-documents',
            'web',
            'tar',
            '-C',
            '/srv/private-documents',
            '-xf',
            '-',
            data=documents,
            binary=True,
        )
        state = (
            'import hashlib, json; from modules.accounts.models import User; '
            'from modules.transport.models import ServiceDay; from modules.uploads.models import Document; '
            'print(json.dumps([User.objects.count(), ServiceDay.objects.count(), '
            'hashlib.sha256(Document.objects.get().file.read()).hexdigest()]))'
        )
        assert self.python(state) == self.python(state, restored=True)
        self.python('from app.runtime_checks import check_runtime; check_runtime()', restored=True)
        self.phase = 'log_privacy'
        self.request(client, '/api/csrf/?code=NaoLogarQueryFicticia')
        logs = self.compose('logs', '--no-color', 'web', 'proxy', 'worker')
        forbidden = [
            'SenhaFicticiaExclusivaDoSmoke!42',
            'RuaFicticiaNaoLogar',
            'NaoLogarQueryFicticia',
            '-26.35',
            '90000000001',
        ]
        forbidden.extend(
            item.value
            for jar in (passenger_cookies, driver_cookies)
            for item in jar
            if item.name.endswith('_token') and item.value
        )
        assert not any(value in logs for value in forbidden)
        print(
            'Readiness/recuperação de serviços, restore PostgreSQL+documento em destinos novos e logs mínimos: OK.',
            flush=True,
        )

    def cleanup(self):
        if self.cli_started:
            args = ['docker', 'ps', '-aq', '--filter', f'label=nextrouter.runtime-cli={self.project}']
            ids = checked(args).split()
            if ids:
                subprocess.run(['docker', 'rm', '--force', *ids], capture_output=True, check=False)
                if checked(args).strip():
                    raise RuntimeError('Não foi possível remover o CLI temporário do próprio teste.')
        if self.owned:
            self.compose('down', '--volumes', '--remove-orphans', timeout=180)
            if self.created_restore_volume:
                exists = subprocess.run(['docker', 'volume', 'inspect', self.restore_volume], capture_output=True)
                if exists.returncode == 0:
                    checked(['docker', 'volume', 'rm', self.restore_volume])
            subprocess.run(['docker', 'image', 'rm', f'nextrouter:{self.revision}'], capture_output=True, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-fictitious', action='store_true', required=True)
    parser.parse_args()
    socket_path = local_socket()

    def interrupt(*_):
        raise KeyboardInterrupt

    previous = {signum: signal.signal(signum, interrupt) for signum in (signal.SIGTERM, signal.SIGINT)}
    failure = None
    try:
        with tempfile.TemporaryDirectory(prefix='nextrouter-runtime-', dir='/tmp/opencode') as directory:
            smoke = Smoke(directory, socket_path)
            try:
                smoke.run()
            except (Exception, KeyboardInterrupt) as exc:
                line = traceback.extract_tb(exc.__traceback__)[-1].lineno
                reason = exc.reason if isinstance(exc, ExternalCommandError) else type(exc).__name__
                failure = f'Smoke falhou na fase {smoke.phase}, linha {line}, tipo {reason}; dados omitidos.'
            finally:
                try:
                    smoke.cleanup()
                except Exception:
                    failure = f'Limpeza incompleta do projeto próprio {smoke.project}; confira os recursos locais.'
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    if failure:
        raise SystemExit(failure)
    print('Smoke local concluído e recursos próprios removidos; não comprova Vue real, navegador ou provedor.')


if __name__ == '__main__':
    main()
