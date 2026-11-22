"""Execute com python -m scripts.frontend_artifact; sem npm ou acesso à rede."""

import argparse
import subprocess
from pathlib import Path

from shared.frontend_artifact import ArtifactError, prepare_artifact, verify_artifact

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / 'frontend'


def _git_head(directory: Path) -> str:
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=directory,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except OSError:
        pass
    return ''


def main():
    parser = argparse.ArgumentParser(
        description='Prepara/verifica entrega de frontend fixada e com hashes preservados.'
    )
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--source', type=Path, default=FRONTEND_DIR / 'dist')
    prepare.add_argument('--destination', type=Path, default=BACKEND_DIR / 'release')
    prepare.add_argument('--frontend-revision', default=_git_head(FRONTEND_DIR))
    prepare.add_argument('--backend-revision', default=_git_head(BACKEND_DIR))
    verify = commands.add_parser('verify')
    verify.add_argument('--root', type=Path, default=BACKEND_DIR / 'frontend_dist')
    verify.add_argument('--backend-revision', default=None)
    options = vars(parser.parse_args())
    command = options.pop('command')
    try:
        if command == 'prepare':
            prepare_artifact(**options)
        else:
            verify_artifact(options['root'], expected_backend_revision=options['backend_revision'])
    except (ArtifactError, OSError):
        parser.exit(
            1, 'Artefato recusado: confira revisões, allowlist, referências e manifesto; nenhum destino foi limpo.\n'
        )
    print('Artefato validado; isso não comprova compilação Vue nem integração em navegador.')


if __name__ == '__main__':
    main()
