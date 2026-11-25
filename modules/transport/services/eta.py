"""Horários de cada parada.

- previsto: gravado ao calcular a rota (OSRM), em ``point_snapshot['_planned_at']``;
- esperado: com a viagem em andamento e a posição do motorista conhecida, é ao vivo:
  agora + tempo de rua da posição atual até a parada, passando pelas paradas abertas antes dela.
  Sobe se o motorista atrasa ou para, desce se ele anda mais rápido que o previsto.
  Sem posição (ou sem serviço de rotas), cai para previsto + atraso atual.
"""

import logging
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)
LIVE_CACHE_SECONDS = 60


def planned_at(stop):
    raw = (stop.point_snapshot or {}).get('_planned_at')
    try:
        return datetime.fromisoformat(raw) if raw else None
    except (TypeError, ValueError):
        return None


def travel_delay_seconds(snapshot, stops=None, now=None):
    """Atraso (em segundos, nunca negativo) da viagem em andamento.

    Parte do atraso na saída, corrige pela última parada atendida e, se a próxima parada
    já passou do horário previsto, usa o atraso que está acontecendo agora.
    """
    travel = snapshot.travel
    if travel.status != 'in_progress':
        return 0
    now = now or timezone.now()
    stops = list(stops if stops is not None else snapshot.stops.all())
    delay = 0.0
    if travel.started_at and snapshot.planned_start:
        delay = (travel.started_at - snapshot.planned_start).total_seconds()
    handled = [stop for stop in stops if stop.handled_at and planned_at(stop)]
    if handled:
        last = max(handled, key=lambda stop: stop.position)
        delay = (last.handled_at - planned_at(last)).total_seconds()
    pending = sorted((stop for stop in stops if not stop.handled_at and planned_at(stop)), key=lambda s: s.position)
    if pending:
        delay = max(delay, (now - planned_at(pending[0])).total_seconds())
    return max(0, round(delay))


def live_offsets(travel):
    """{id da parada aberta: segundos a partir da posição atual}, ou None sem dados ao vivo.

    Guardado por posição recebida: várias leituras (motorista, passageiros, empresa) entre duas
    posições usam a mesma conta e não chamam o serviço de rotas de novo.
    """
    if travel.status != 'in_progress' or travel.location_updated_at is None:
        return None
    key = f'travel_live_eta:{travel.pk}:{travel.location_updated_at.timestamp()}'
    cached = cache.get(key)
    if cached is not None:
        return {int(stop_id): seconds for stop_id, seconds in cached.items()}
    from modules.transport.services.tracking import live_legs

    try:
        legs = live_legs(travel)
    except Exception:  # serviço de rotas fora ou ponto inválido: usa previsto + atraso
        logger.warning('eta_live_unavailable', extra={'travel_id': travel.pk})
        return None
    offsets, total = {}, 0.0
    for stop, result in legs:
        total += result['duration_seconds'] if result else 0
        offsets[stop.pk] = round(total)
    cache.set(key, offsets, LIVE_CACHE_SECONDS)
    return offsets


def stop_expectations(snapshot, stops=None, now=None):
    """({id da parada: horário esperado}, atraso em segundos) para todas as paradas do percurso."""
    now = now or timezone.now()
    stops = list(stops if stops is not None else snapshot.stops.all())
    delay = travel_delay_seconds(snapshot, stops, now=now)
    live = live_offsets(snapshot.travel) if snapshot.travel.status == 'in_progress' else None
    result = {}
    for stop in stops:
        if stop.handled_at:
            result[stop.pk] = stop.handled_at
        elif live and stop.pk in live:
            result[stop.pk] = now + timedelta(seconds=live[stop.pk])
        else:
            result[stop.pk] = expected_at(stop, delay)
    if live:
        # Atraso mostrado = o da próxima parada aberta em relação ao previsto (nunca negativo).
        nxt = min((stop for stop in stops if stop.pk in live), key=lambda stop: stop.position, default=None)
        planned = planned_at(nxt) if nxt else None
        delay = max(0, round((result[nxt.pk] - planned).total_seconds())) if planned else 0
    return result, delay


def expected_at(stop, delay_seconds):
    if stop.handled_at:
        return stop.handled_at
    planned = planned_at(stop)
    return planned + timedelta(seconds=delay_seconds) if planned else None


def _iso(value):
    return value.isoformat() if value else None


def participation_timing(participation):
    """Previsão da parada do passageiro no percurso publicado (ou atual) da viagem.

    Devolve o horário previsto e o esperado da parada dele, quantas paradas ainda faltam
    antes dela e o horário esperado de chegada ao fim do percurso. Nada sobre outros passageiros.
    """
    travel = participation.travel
    snapshot = travel.published_snapshot or travel.current_snapshot
    if snapshot is None:
        return None
    stops = list(snapshot.stops.order_by('position'))
    # Na ida importa onde ele embarca; na volta, onde ele desce (a parada comum tem todos).
    operation = 'board' if participation.leg == 'outbound' else 'drop'
    mine = next(
        (
            stop
            for stop in stops
            if any(p.participation_id == participation.pk and p.operation == operation for p in stop.participants.all())
        ),
        None,
    )
    if mine is None:
        return None
    expected, delay = stop_expectations(snapshot, stops)
    ahead = sum(1 for stop in stops if stop.position < mine.position and not stop.handled_at)
    last = stops[-1]
    return {
        'stop_position': mine.position,
        'stops_ahead': ahead,
        'planned_at': _iso(planned_at(mine)),
        'expected_at': _iso(expected[mine.pk]),
        'arrival_expected_at': _iso(expected[last.pk]),
        'delay_seconds': delay,
    }
