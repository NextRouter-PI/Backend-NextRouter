"""Mapa geral da empresa: todas as viagens em andamento com posição, progresso e atraso."""

from modules.organizations.models import Company
from modules.transport.models import Travel
from modules.transport.services.eta import stop_expectations


def live_travels_for_company_owner(user):
    """Só o dono (usuário) de empresas operacionais vê; nada de outras empresas."""
    companies = Company.objects.operational_for(user)
    travels = (
        Travel.objects
        .dated()
        .filter(company__in=companies, status=Travel.Status.IN_PROGRESS)
        .select_related(
            'service__route_group',
            'driver__user',
            'vehicle',
            'published_snapshot',
            'current_snapshot',
        )
        .prefetch_related('participations')
        .order_by('started_at', 'pk')
    )
    return [_row(travel) for travel in travels]


def _row(travel):
    snapshot = travel.published_snapshot or travel.current_snapshot
    stops = list(snapshot.stops.order_by('position')) if snapshot else []
    expected, delay = stop_expectations(snapshot, stops) if snapshot else ({}, 0)
    pending = [stop for stop in stops if not stop.handled_at]
    nxt = pending[0] if pending else None
    participations = [p for p in travel.participations.all() if p.status in ('allocated', 'on_board', 'dropped_off')]
    return {
        'id': travel.pk,
        'direction': travel.service.direction,
        'group_name': getattr(travel.service.route_group, 'name', '') or '',
        'service_name': travel.service.name or '',
        'driver_name': travel.driver.user.name if travel.driver_id else '',
        'vehicle_plate': travel.vehicle.plate if travel.vehicle_id else '',
        'started_at': travel.started_at,
        'planned_end': travel.planned_end,
        'latitude': travel.current_latitude,
        'longitude': travel.current_longitude,
        'location_updated_at': travel.location_updated_at,
        'geometry': snapshot.geometry if snapshot else None,
        'boarded': sum(1 for p in participations if p.status in ('on_board', 'dropped_off')),
        'waiting': sum(1 for p in participations if p.status == 'allocated'),
        'total': len(participations),
        'stops_done': len(stops) - len(pending),
        'stops_total': len(stops),
        'delay_seconds': delay,
        'next_stop_name': (nxt.point_snapshot or {}).get('name', '') if nxt else '',
        'next_stop_expected_at': expected.get(nxt.pk) if nxt else None,
    }
