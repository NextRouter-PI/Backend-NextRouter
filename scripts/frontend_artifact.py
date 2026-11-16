"""Execute com python -m scripts.frontend_artifact; sem npm ou acesso à rede."""

import argparse
from pathlib import Path

from shared.frontend_artifact import ArtifactError, prepare_artifact, verify_artifact


def main():
    parser = argparse.ArgumentParser(
        description='Prepara/verifica entrega de frontend fixada e com hashes preservados.'
    )
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--source', type=Path, required=True)
    prepare.add_argument('--destination', type=Path, required=True)
    prepare.add_argument('--frontend-revision', required=True)
    prepare.add_argument('--backend-revision', required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('--root', type=Path, required=True)
    verify.add_argument('--backend-revision', required=True)
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
