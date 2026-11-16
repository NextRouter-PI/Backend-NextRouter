import json
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from shared.frontend_artifact import ArtifactError, inspect_artifact, prepare_artifact, verify_artifact


class PreparedArtifactTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='nextrouter-artifact-', dir='/tmp/opencode')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'dist'
        (self.source / 'assets').mkdir(parents=True)
        (self.source / 'index.html').write_text(
            '<!doctype html><script type="module" src="/assets/index-Hash.js"></script>'
        )
        (self.source / 'assets/index-Hash.js').write_text('/* somente fixture, não Vue real */')
        self.destination = self.root / 'release'

    def prepare(self, **extra):
        return prepare_artifact(**{
            'source': self.source,
            'destination': self.destination,
            'frontend_revision': 'a' * 40,
            'backend_revision': 'b' * 40,
            **extra,
        })

    def test_preparation_preserves_names_and_is_reproducible_without_timestamp(self):
        first = self.prepare()
        second = self.prepare(destination=self.root / 'second')
        self.assertEqual(first, second)
        self.assertEqual(verify_artifact(self.destination / 'frontend_dist', expected_backend_revision='b' * 40), first)
        self.assertTrue((self.destination / 'frontend_dist/assets/index-Hash.js').is_file())
        self.assertFalse((self.destination / 'frontend_dist/frontend-release.json').exists())

    def test_existing_destination_and_mutable_revisions_are_rejected(self):
        self.prepare()
        for extra in ({}, {'frontend_revision': 'main'}, {'backend_revision': '1234'}):
            with self.subTest(extra=extra), self.assertRaises(ArtifactError):
                self.prepare(**extra)
        self.assertTrue((self.destination / 'frontend_dist/index.html').is_file())

    def test_hidden_files_maps_manifests_and_symlinks_are_not_silently_published(self):
        for name in ('.env', 'assets/code.js.map', 'assets/manifest.json', 'sw.js', 'assets/.hidden.js'):
            path = self.source / name
            path.write_text('fixture')
            with self.subTest(name=name), self.assertRaises(ArtifactError):
                self.prepare()
            path.unlink()
        (self.source / 'assets/link.js').symlink_to(self.source / 'index.html')
        with self.assertRaises(ArtifactError):
            self.prepare()
        self.assertFalse(self.destination.exists())

    def test_missing_external_and_traversal_references_are_rejected(self):
        for reference in (
            '/assets/missing.js',
            'https://external.invalid/app.js',
            '/assets/../private.js',
            '/static/app.js',
        ):
            (self.source / 'index.html').write_text(f'<script src="{reference}"></script>')
            with self.subTest(reference=reference), self.assertRaises(ArtifactError):
                self.prepare()

    def test_tampering_added_file_and_backend_mismatch_are_detected(self):
        self.prepare()
        root = self.destination / 'frontend_dist'
        with self.assertRaises(ArtifactError):
            verify_artifact(root, expected_backend_revision='c' * 40)
        (root / 'assets/new.js').write_text('fixture')
        with self.assertRaises(ArtifactError):
            verify_artifact(root)
        metadata = json.loads((self.destination / 'frontend-release.json').read_text())
        self.assertEqual(set(metadata['files']), set(inspect_artifact(self.source)))

    def test_source_cannot_be_destination_or_contain_destination(self):
        for destination in (self.source, self.source / 'nested'):
            with self.subTest(destination=destination), self.assertRaises(ArtifactError):
                self.prepare(destination=destination)
