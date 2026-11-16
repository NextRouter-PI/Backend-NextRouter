import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings


class FrontendArtifactTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory(prefix='nextrouter-spa-', dir='/tmp/opencode')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / 'assets').mkdir()
        (self.root / 'index.html').write_text('<!doctype html><div>{{ vueExpression }}</div>')
        (self.root / 'assets/index-A1b2C3d4.js').write_text('console.log("fixture");')
        (self.root / 'assets/theme.css').write_text('body { color: black; }')
        (self.root / 'assets/index-A1b2C3d4.js.map').write_text('private source map')
        (self.root / 'assets/.secret.js').write_text('not public')
        (self.root / 'assets/manifest.json').write_text('{}')
        (self.root / 'assets/secret.js').symlink_to(self.root / 'index.html')
        (self.root / '.env').write_text('FIXTURE_NOT_A_SECRET=yes')
        (self.root / 'favicon.ico').write_bytes(b'fixture-icon')
        override = override_settings(FRONTEND_DIST=self.root, WHITENOISE_USE_FINDERS=False)
        override.enable()
        self.addCleanup(override.disable)

    def test_navigation_html_deep_links_head_and_vue_expressions_are_not_templates(self):
        for url in ('/', '/viagens/123', '/unknown-ui-route'):
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_ACCEPT='text/html')
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '{{ vueExpression }}')
                self.assertEqual(response['Cache-Control'], 'no-cache')
        response = self.client.head('/viagens/123', HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')
        self.assertGreater(int(response['Content-Length']), 0)

    def test_reserved_prefixes_missing_files_and_non_html_never_receive_spa(self):
        for url in (
            '/api',
            '/api/not-real/',
            '/admin/not-real/',
            '/ws',
            '/ws/nope/',
            '/static/not-real.js',
            '/assets',
            '/assets/not-real.js',
            '/assets/no-extension',
            '/media/no-file',
            '/downloads/no-file',
            '/uploads/no-file',
            '/html-template-test',
            '/frontend_dist/index.html',
            '/.env',
            '/missing.ico',
        ):
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_ACCEPT='text/html')
                self.assertNotEqual(response.status_code, 200)
                self.assertNotIn(b'vueExpression', response.content)
        self.assertEqual(self.client.get('/viagens/123', HTTP_ACCEPT='application/json').status_code, 404)
        self.assertEqual(self.client.post('/viagens/123', HTTP_ACCEPT='text/html').status_code, 405)

    def test_only_allowlisted_assets_are_served_with_original_hash_and_cache(self):
        response = self.client.get('/assets/index-A1b2C3d4.js')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'public, max-age=0, must-revalidate')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        response.close()
        response = self.client.get('/assets/theme.css')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('immutable', response['Cache-Control'])
        etag = response['ETag']
        response.close()
        self.assertEqual(self.client.get('/assets/theme.css', HTTP_IF_NONE_MATCH=etag).status_code, 304)
        for suffix in ('index-A1b2C3d4.js.map', '.secret.js', 'manifest.json', 'secret.js', '../.env', '%2e%2e/.env'):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.client.get(f'/assets/{suffix}').status_code, 404)

    def test_missing_build_is_404_and_private_api_is_never_publicly_cached(self):
        with override_settings(FRONTEND_DIST=self.root / 'missing'):
            self.assertEqual(self.client.get('/', HTTP_ACCEPT='text/html').status_code, 404)
        response = self.client.get('/api/csrf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertIn('Cookie', response['Vary'])
        icon = self.client.get('/favicon.ico')
        self.assertEqual(icon.status_code, 200)
        self.assertNotIn('immutable', icon['Cache-Control'])
