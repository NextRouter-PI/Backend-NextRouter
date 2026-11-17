import json
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from drf_spectacular.generators import SchemaGenerator

from app.html_templates import FILES

ROOT = settings.BASE_DIR / 'html-template-test'


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.scripts = []
        self.page = None
        self.ids = []
        self.styling = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'script':
            self.scripts.append(attrs.get('src', ''))
        if tag == 'body':
            self.page = attrs.get('data-page')
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'style' or 'style' in attrs or (tag == 'link' and attrs.get('rel') == 'stylesheet'):
            self.styling.append(tag)


@override_settings(DEBUG=True)
class HtmlTemplateDeliveryTests(SimpleTestCase):
    def test_only_allowlisted_files_and_index_are_served_without_cache_or_styles(self):
        self.assertEqual(self.client.get('/html-template-test/').status_code, 200)
        for name in FILES:
            with self.subTest(name=name):
                response = self.client.get(f'/html-template-test/{name}')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Cache-Control'], 'private, no-store')
                self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
                self.assertEqual(response['Referrer-Policy'], 'same-origin')
                self.assertIn("style-src 'none'", response['Content-Security-Policy'])
                self.assertIn("script-src 'self'", response['Content-Security-Policy'])
                self.assertEqual(int(response['Content-Length']), len(response.content))
                head = self.client.head(f'/html-template-test/{name}')
                self.assertEqual(head.status_code, 200)
                self.assertEqual(head.content, b'')
                self.assertEqual(head['Content-Length'], response['Content-Length'])
                self.assertEqual(self.client.post(f'/html-template-test/{name}').status_code, 405)

    def test_production_denies_every_file_even_if_client_exists(self):
        with override_settings(DEBUG=False):
            for name in ('', *FILES):
                with self.subTest(name=name):
                    self.assertEqual(self.client.get(f'/html-template-test/{name}').status_code, 404)

    def test_unlisted_private_traversal_and_missing_files_never_receive_html(self):
        for name in (
            'README.md',
            'COBERTURA.md',
            '.env',
            'assets/',
            'assets/missing.js',
            'assets/private.json',
            '../.env',
            '%2e%2e/.env',
            'assets/../../db.sqlite3',
            'index.html/extra',
            'missing.html',
        ):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(f'/html-template-test/{name}').status_code, 404)
        self.assertEqual(self.client.get('/api/not-a-real-endpoint/').status_code, 404)
        self.assertEqual(self.client.get('/assets/not-real.js').status_code, 404)

    def test_allowlist_does_not_follow_symlinks(self):
        with tempfile.TemporaryDirectory(prefix='nr-html-files-', dir='/tmp/opencode') as directory:
            root = Path(directory)
            folder = root / 'html-template-test'
            folder.mkdir()
            (root / 'private.html').write_text('FIXTURE_PRIVATE')
            (folder / 'index.html').symlink_to(root / 'private.html')
            with patch('app.html_templates.settings.BASE_DIR', root):
                self.assertEqual(self.client.get('/html-template-test/').status_code, 404)

    def test_client_is_not_in_static_collection_or_runtime(self):
        self.assertNotIn(ROOT, settings.STATICFILES_DIRS)
        self.assertNotEqual(ROOT, settings.FRONTEND_DIST)
        self.assertIn('html-template-test/', (settings.BASE_DIR / '.dockerignore').read_text().splitlines())

    def test_html_navigation_module_sources_and_no_styling(self):
        metadata = json.loads((ROOT / 'assets/workflows.json').read_text())
        pages = metadata['pages']
        self.assertEqual({item['file'] for item in pages}, {name for name in FILES if name.endswith('.html')})
        for item in pages:
            with self.subTest(page=item['file']):
                parser = PageParser()
                parser.feed((ROOT / item['file']).read_text())
                self.assertEqual(parser.page, item['key'])
                self.assertEqual(parser.styling, [])
                self.assertEqual(parser.scripts, ['assets/site.js'])
                self.assertIn('workspace', parser.ids)
                self.assertIn('session', parser.ids)
                self.assertEqual(len(parser.ids), len(set(parser.ids)))
                for link in parser.links:
                    if not link.startswith('/'):
                        self.assertIn(link, FILES)

    def test_workflows_reference_only_current_schema_operations(self):
        schema = SchemaGenerator().get_schema(public=True)
        metadata = json.loads((ROOT / 'assets/workflows.json').read_text())
        for page in metadata['pages']:
            for resource in page['resources']:
                self.assertIn('get', schema['paths'][f'/api/{resource}/'])
            for operation in page['operations']:
                method, path = operation.split(' ')
                self.assertIn(method.lower(), schema['paths'][path])
        for key in ('paths', 'route-schedules', 'confirmations'):
            self.assertNotIn(f'/api/{key}/', schema['paths'])
        for name in FILES:
            content = (ROOT / name).read_text()
            for forbidden in (
                'localStorage',
                'sessionStorage',
                "headers['Authorization']",
                'innerHTML',
                'http://localhost:8000',
            ):
                self.assertNotIn(forbidden, content, name)

    def test_native_javascript_regressions_when_node_is_available(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node ausente; o cliente não depende dele em runtime, mas os testes JS exigem Node >=22.')
        version = subprocess.check_output([node, '--version'], text=True).strip()
        if int(version.removeprefix('v').split('.')[0]) < 22:
            self.skipTest('Testes JS opcionais exigem Node >=22; não instalar/atualizar dependências automaticamente.')
        result = subprocess.run(
            [node, '--test', 'tests/html_client.test.mjs'],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_browser_smoke_refuses_to_prepare_data_without_explicit_confirmation(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node ausente; smoke de navegador é opcional.')
        version = subprocess.check_output([node, '--version'], text=True).strip()
        if int(version.removeprefix('v').split('.')[0]) < 22:
            self.skipTest('Smoke opcional exige Node >=22.')
        result = subprocess.run(
            [node, 'scripts/test_html_browser.mjs'],
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Exige --confirm-fictitious', result.stderr)
