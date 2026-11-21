"""Orquestrador HTTP + WebSocket para simular a corrida em tempo real."""

import json
import time
from datetime import UTC, datetime
from math import hypot
from urllib.parse import urlsplit
from uuid import uuid4

import requests

from .scenarios import interpolate_route
from .ws_client import SimpleWebSocketClient


class DriverApiSession:
    """Sessão autenticada do motorista usando cookies HttpOnly + X-CSRFToken na mesma origem."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.csrf_token = ''

    def _refresh_csrf(self):
        resp = self.session.get(f'{self.base_url}/api/csrf/', timeout=10)
        resp.raise_for_status()
        self.csrf_token = resp.json().get('csrfToken') or self.session.cookies.get('csrftoken', '')

    def post(self, path: str, payload: dict | None = None) -> dict:
        if not self.csrf_token:
            self._refresh_csrf()
        resp = self.session.post(
            f'{self.base_url}{path}',
            json=payload if payload is not None else {},
            headers={
                'X-CSRFToken': self.csrf_token,
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/',
            },
            timeout=15,
        )
        if not resp.ok:
            raise RuntimeError(f'POST {path} falhou ({resp.status_code}): {resp.text[:300]}')
        if 'csrftoken' in self.session.cookies:
            self.csrf_token = self.session.cookies['csrftoken']
        return resp.json() if resp.content else {}

    def login(self, email: str, password: str):
        self._refresh_csrf()
        self.post('/api/login/', {'email': email, 'password': password})
        self._refresh_csrf()

    def cookie_header(self) -> str:
        return '; '.join(f'{c.name}={c.value}' for c in self.session.cookies)


def _assign_stop_steps(points: list[tuple[float, float]], stops: list[dict]) -> dict[int, list[dict]]:
    """Mapeia cada parada ao passo mais próximo ao longo do trajeto interpolado."""
    total = len(points)
    mapping: dict[int, list[dict]] = {}
    last_idx = 0
    for idx_stop, stop in enumerate(stops):
        lat = stop.get('latitude')
        lng = stop.get('longitude')
        if lat is None or lng is None:
            step = min(total - 1, max(last_idx, round((idx_stop + 1) / (len(stops) + 1) * (total - 1))))
        else:
            best_step = last_idx
            best_dist = float('inf')
            for step_idx in range(last_idx, total):
                p_lat, p_lng = points[step_idx]
                dist = hypot(p_lat - float(lat), p_lng - float(lng))
                if dist < best_dist:
                    best_dist = dist
                    best_step = step_idx
            step = best_step
        last_idx = step
        mapping.setdefault(step, []).append(stop)
    return mapping


def _format_clock(seconds: float) -> str:
    mins, secs = divmod(max(0, int(seconds)), 60)
    return f'{mins:02d}:{secs:02d}'


def run_simulation(plan: dict, *, base_url: str, duration_seconds: int, interval_seconds: float):
    """Executa a viagem completa: start -> streaming GPS via WS -> paradas/presença -> finish."""
    if interval_seconds < 2.1:
        raise ValueError('interval_seconds deve ser >= 2.1s para respeitar LOCATION_MIN_INTERVAL_SECONDS=2.')

    steps = max(2, round(duration_seconds / interval_seconds) + 1)
    points = interpolate_route(plan['geometry_coords'], steps)
    stop_schedule = _assign_stop_steps(points, plan['stops'])

    api = DriverApiSession(base_url)
    print(f'-> Autenticando motorista ({plan["driver_email"]}) em {base_url}...')
    api.login(plan['driver_email'], plan['driver_password'])

    travel_id = plan['travel_id']
    print(f'-> Iniciando viagem #{travel_id} ({plan["label"]})...')
    api.post(f'/api/travels/{travel_id}/start/', {'expected_revision': plan['travel_revision']})

    parsed = urlsplit(base_url)
    ws_url = f'ws://{parsed.netloc}/ws/travels/{travel_id}/location/'
    ws = SimpleWebSocketClient(ws_url, origin=base_url.rstrip('/'), cookie_header=api.cookie_header())
    ws.connect()
    print(f'-> WebSocket conectado ({ws_url}). Simulando {duration_seconds}s em {steps} pontos...\n')

    started_at = time.monotonic()
    try:
        for step_idx, (lat, lng) in enumerate(points):
            now_iso = datetime.now(UTC).isoformat()
            ws.send_text(json.dumps({'latitude': lat, 'longitude': lng, 'recorded_at': now_iso}))
            elapsed = time.monotonic() - started_at
            pct = round((step_idx / (steps - 1)) * 100)
            print(
                f'[{_format_clock(elapsed)} / {_format_clock(duration_seconds)}] {pct:3d}% · GPS ({lat:.5f}, {lng:.5f})'
            )

            stops_here = stop_schedule.get(step_idx, [])
            if stops_here:
                # Pequeno respiro para o SQLite concluir o commit de save_location do WebSocket.
                time.sleep(0.35)
            for stop in stops_here:
                for participant in stop['participants']:
                    kind = 'boarded' if participant['operation'] == 'board' else 'dropped_off'
                    api.post(
                        f'/api/travel-participations/{participant["participation_id"]}/record/',
                        {'kind': kind, 'operation_id': str(uuid4())},
                    )
                    verb = 'Embarque' if kind == 'boarded' else 'Desembarque'
                    print(f'   ✓ {verb} registrado: {participant["passenger_name"]}')
                api.post(f'/api/route-stops/{stop["id"]}/handle/', {'skipped': False})
                print(f'   ✓ Parada #{stop["position"]} atendida: {stop["name"]}')

            if step_idx < steps - 1:
                target_elapsed = (step_idx + 1) * (duration_seconds / (steps - 1))
                sleep_for = max(2.05, target_elapsed - (time.monotonic() - started_at))
                time.sleep(sleep_for)

        print(f'\n-> Finalizando viagem #{travel_id}...')
        api.post(f'/api/travels/{travel_id}/finish/', {})
        print('✓ Viagem finalizada com sucesso! O acompanhamento ao vivo foi encerrado na tela do passageiro.')
    finally:
        ws.close()
