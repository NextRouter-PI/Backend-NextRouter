"""Contrato de artefato offline; não importa Django nem executa código do frontend."""

import hashlib
import json
import re
import shutil
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ASSET_EXTENSIONS = {
    '.js',
    '.css',
    '.svg',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.webp',
    '.avif',
    '.ico',
    '.woff',
    '.woff2',
    '.ttf',
    '.eot',
    '.wasm',
}
MANIFEST_NAME = 'frontend-release.json'
MAX_ARTIFACT_BYTES = 256 * 1024 * 1024


class ArtifactError(ValueError):
    pass


def revision(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', value):
        raise ArtifactError('Informe a revisão Git completa e minúscula, não branch/tag mutável.')
    return value


class References(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        names = ('src',) if tag in ('script', 'img', 'source') else ('href',) if tag == 'link' else ()
        for name in names:
            if value := attributes.get(name):
                parsed = urlsplit(value)
                path = unquote(parsed.path)
                if (
                    parsed.scheme
                    or parsed.netloc
                    or parsed.query
                    or parsed.fragment
                    or not (path.startswith('/assets/') or path == '/favicon.ico')
                    or any(part in ('', '.', '..') for part in path.lstrip('/').split('/'))
                ):
                    raise ArtifactError('Referências de recursos devem usar /assets/ ou /favicon.ico da mesma origem.')
                self.paths.append(path.lstrip('/'))


def inspect_artifact(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ArtifactError('O artefato deve ser um diretório real, sem symlinks.')
    files = {}
    total = 0
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if path.is_symlink() or any(
            part.startswith('.') or '\\' in part or any(ord(char) < 32 for char in part) for part in relative.parts
        ):
            raise ArtifactError('Artefato contém caminho oculto, inválido ou symlink.')
        if path.is_dir():
            if relative.parts[0] != 'assets':
                raise ArtifactError('Somente a árvore assets é permitida além do HTML/favicon.')
            continue
        if not path.is_file() or not (
            relative.as_posix() in ('index.html', 'favicon.ico')
            or (relative.parts[0] == 'assets' and path.suffix.lower() in ASSET_EXTENSIONS)
        ):
            raise ArtifactError(
                'Artefato contém arquivo não autorizado; exclua mapas, manifestos e arquivos de desenvolvimento.'
            )
        total += path.stat().st_size
        if total > MAX_ARTIFACT_BYTES or len(files) >= 25000:
            raise ArtifactError('Artefato excede o limite técnico de tamanho/quantidade.')
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if 'index.html' not in files or not any(name.startswith('assets/') for name in files):
        raise ArtifactError('Artefato exige index.html e assets compilados.')
    references = References()
    try:
        references.feed((root / 'index.html').read_text(encoding='utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise ArtifactError('HTML inválido ou referências incompatíveis com o contrato.') from exc
    if not references.paths or any(path not in files for path in references.paths):
        raise ArtifactError('HTML deve referenciar recursos existentes no artefato.')
    return files


def prepare_artifact(*, source, destination, frontend_revision, backend_revision):
    source, destination = Path(source), Path(destination)
    revision(frontend_revision)
    revision(backend_revision)
    if destination.exists() or destination.is_symlink() or destination.resolve().is_relative_to(source.resolve()):
        raise ArtifactError('Use uma nova pasta de entrega fora da origem; não sobreponha artefatos.')
    before = inspect_artifact(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.nextrouter-artifact-', dir=destination.parent) as temporary:
        prepared = Path(temporary) / 'release'
        shutil.copytree(source, prepared / 'frontend_dist', symlinks=True)
        if inspect_artifact(prepared / 'frontend_dist') != before:
            raise ArtifactError('O artefato foi alterado durante a cópia.')
        metadata = {
            'schema_version': 1,
            'frontend_revision': frontend_revision,
            'backend_revision': backend_revision,
            'files': before,
        }
        (prepared / MANIFEST_NAME).write_text(json.dumps(metadata, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        # mkdir exclusivo reserva o destino sem a corrida de rename sobre pasta vazia alheia.
        destination.mkdir()
        for path in sorted((prepared / 'frontend_dist').rglob('*')):
            target = destination / path.relative_to(prepared)
            if path.is_dir():
                target.mkdir(parents=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with path.open('rb') as origin, target.open('xb') as output:
                    shutil.copyfileobj(origin, output)
        # Manifesto por último: uma interrupção deixa uma entrega incompleta recusável.
        with (destination / MANIFEST_NAME).open('x', encoding='utf-8') as output:
            output.write((prepared / MANIFEST_NAME).read_text(encoding='utf-8'))
    return metadata


def verify_artifact(root, *, expected_backend_revision=None):
    root = Path(root)
    manifest = root.parent / MANIFEST_NAME
    if manifest.is_symlink() or not manifest.is_file():
        raise ArtifactError('Manifesto de release ausente ou inválido.')
    try:
        metadata = json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(metadata, dict) or metadata.get('schema_version') != 1:
            raise ArtifactError('Versão de manifesto desconhecida.')
        revision(metadata.get('frontend_revision'))
        revision(metadata.get('backend_revision'))
        if expected_backend_revision is not None and metadata['backend_revision'] != revision(
            expected_backend_revision
        ):
            raise ArtifactError('Frontend e backend não pertencem à mesma entrega identificada.')
        if metadata.get('files') != inspect_artifact(root):
            raise ArtifactError('Artefato diferente do manifesto; não misture chunks de entregas.')
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactError('Não foi possível validar o manifesto de release.') from exc
    return metadata
