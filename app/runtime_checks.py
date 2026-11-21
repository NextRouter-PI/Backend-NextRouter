"""Probes sem dados de negócio e sem refletir exceções/URLs em respostas ou logs."""

import tempfile
from pathlib import Path
from time import monotonic
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import storages
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from shared.frontend_artifact import verify_artifact

STORAGE_PROBE_TTL_SECONDS = 15.0
_STORAGE_PROBE_OK_UNTIL: dict[str, float] = {}


def _check_private_storage() -> None:
    directory = Path(settings.PRIVATE_DOCUMENT_ROOT)
    if not directory.is_absolute() or not directory.is_dir():
        raise RuntimeError('storage_unavailable')
    key = str(directory.resolve())
    now = monotonic()
    if _STORAGE_PROBE_OK_UNTIL.get(key, 0.0) > now:
        return
    with tempfile.TemporaryFile(dir=directory) as probe:
        probe.write(b'nextrouter-storage-probe')
        probe.flush()
        probe.seek(0)
        if probe.read() != b'nextrouter-storage-probe':
            raise RuntimeError('storage_unavailable')
    _STORAGE_PROBE_OK_UNTIL[key] = now + STORAGE_PROBE_TTL_SECONDS


def check_dependencies():
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        if cursor.fetchone() != (1,):
            raise RuntimeError('database_unavailable')
    key = f'health:{uuid4().hex}'
    try:
        cache.set(key, 'ok', timeout=10)
        if cache.get(key) != 'ok':
            raise RuntimeError('cache_unavailable')
    finally:
        cache.delete(key)
    _check_private_storage()


def check_staticfiles():
    # Instanciar o storage valida o JSON; a abertura também recusa manifesto ausente.
    storage = storages['staticfiles']
    with storage.open(storage.manifest_name) as manifest:
        if not manifest.read(1):
            raise RuntimeError('staticfiles_unavailable')


def check_runtime(*, require_frontend=True):
    check_dependencies()
    executor = MigrationExecutor(connection)
    executor.loader.check_consistent_history(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise RuntimeError('migrations_pending')
    check_staticfiles()
    if require_frontend:
        verify_artifact(settings.FRONTEND_DIST, expected_backend_revision=settings.BACKEND_REVISION)
