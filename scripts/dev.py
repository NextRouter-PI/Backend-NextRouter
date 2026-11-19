"""Servidor local independente. Não instala, compila, migra ou cria dados."""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Django/Daphne local na porta 8000, com configuração opcional no .env.')
    parser.add_argument('--lan-host', metavar='IP', help='IPv4 da máquina na rede confiável; autoriza também Vite :5173.')
    parser.add_argument('--noreload', action='store_true', help='Desliga o autoreload do backend.')
    args = parser.parse_args()
    # Sobrescrever, não setdefault: uma configuração de produção herdada não muda este comando.
    os.environ['DJANGO_SETTINGS_MODULE'] = 'app.settings.dev'
    os.environ['NEXTROUTER_LAN_HOST'] = args.lan_host or ''
    backend = Path(__file__).resolve().parents[1]
    os.chdir(backend)
    address = '0.0.0.0:8000' if args.lan_host else '127.0.0.1:8000'
    command = [sys.executable, str(backend / 'manage.py'), 'runserver', address, '--settings=app.settings.dev']
    if args.noreload:
        command.append('--noreload')
    os.execv(sys.executable, command)


if __name__ == '__main__':
    main()
