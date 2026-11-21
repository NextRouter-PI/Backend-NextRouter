"""CLI do simulador modular de percurso de viagem.

Exemplos:
  pdm run simulate-trip --scenario outbound --duration 120 --reset-db --confirm-fictitious
  pdm run simulate-trip --scenario return --duration 120 --reset-db --confirm-fictitious
"""

import argparse
import os
import sys

import httpx


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Recria o banco local fictício e simula um percurso completo com GPS ao vivo via WebSocket.'
    )
    parser.add_argument('--scenario', default='outbound', choices=('outbound', 'return'))
    parser.add_argument('--duration', type=int, default=120, help='Duração total da corrida em segundos (padrão: 120).')
    parser.add_argument(
        '--interval', type=float, default=2.5, help='Intervalo entre envios de GPS em segundos (mínimo: 2.1).'
    )
    parser.add_argument('--base-url', default='http://127.0.0.1:8000', help='URL do servidor Django/Daphne local.')
    parser.add_argument('--reset-db', action='store_true', help='Apaga backend/dev.sqlite3 e recria do zero.')
    parser.add_argument(
        '--confirm-fictitious', action='store_true', help='Confirmação obrigatória para resetar o banco fictício.'
    )
    parser.add_argument('--prepare-only', action='store_true', help='Apenas prepara o banco/viagem sem iniciar a rota.')
    parser.add_argument('--no-wait', action='store_true', help='Inicia a corrida imediatamente sem aguardar ENTER.')
    return parser.parse_args(argv)


def _check_server_live(base_url: str) -> bool:
    try:
        resp = httpx.get(f'{base_url.rstrip("/")}/health/live/', timeout=3)
        return resp.is_success
    except httpx.HTTPError:
        return False


def main(argv=None):
    args = parse_args(argv)
    if args.duration < 10:
        raise SystemExit('Erro: --duration deve ser >= 10 segundos.')
    if args.interval < 2.1:
        raise SystemExit('Erro: --interval deve ser >= 2.1 segundos.')

    os.environ['DJANGO_SETTINGS_MODULE'] = 'app.settings.dev'
    import django

    django.setup()

    from .database import prepare_scenario, reset_local_sqlite
    from .runner import run_simulation
    from .scenarios import get_scenario

    scenario = get_scenario(args.scenario)
    if args.reset_db:
        db_path = reset_local_sqlite(confirm_fictitious=args.confirm_fictitious)
        print(f'✓ Banco local recriado do zero: {db_path}')

    plan = prepare_scenario(scenario)
    route_source = 'OSRM real' if plan['used_osrm'] else 'polilinha offline realista'
    print('\n=== Cenário pronto para acompanhamento ===')
    print(f'  Cenário:    {plan["label"]} ({route_source})')
    print(f'  Viagem:     #{plan["travel_id"]} (publicada, revisão {plan["travel_revision"]})')
    print(f'  Passageiro: {plan["passenger_email"]} / {plan["passenger_password"]}')
    print(f'  Motorista:  {plan["driver_email"]} / {plan["driver_password"]}')
    print(f'  Empresa:    {plan["company_email"]} / {plan["company_password"]}')
    print('  Frontend:   http://127.0.0.1:5173')
    print('==========================================\n')

    if args.prepare_only:
        return

    if args.reset_db:
        print('ATENÇÃO: como dev.sqlite3 foi recriado, inicie (ou reinicie) `pdm run dev` antes de continuar.')

    if not args.no_wait:
        input('Faça login como passageiro na Home (http://127.0.0.1:5173) e pressione ENTER para iniciar a corrida... ')

    if not _check_server_live(args.base_url):
        raise SystemExit(
            f'Servidor não encontrado em {args.base_url}. Inicie `pdm run dev` em outro terminal e tente novamente.'
        )

    run_simulation(
        plan,
        base_url=args.base_url,
        duration_seconds=args.duration,
        interval_seconds=args.interval,
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nSimulação interrompida pelo usuário.')
        sys.exit(130)
