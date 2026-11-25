"""Horários de cada parada.

- previsto: gravado ao calcular a rota (OSRM), em ``point_snapshot['_planned_at']``;
- esperado: previsto + atraso atual da viagem, recalculado a cada leitura durante a viagem.
"""

from datetime import datetime, timedelta

from django.utils import timezone


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
    delay = travel_delay_seconds(snapshot, stops)
    ahead = sum(1 for stop in stops if stop.position < mine.position and not stop.handled_at)
    last = stops[-1]
    return {
        'stop_position': mine.position,
        'stops_ahead': ahead,
        'planned_at': _iso(planned_at(mine)),
        'expected_at': _iso(expected_at(mine, delay)),
        'arrival_expected_at': _iso(expected_at(last, delay)),
        'delay_seconds': delay,
    }
