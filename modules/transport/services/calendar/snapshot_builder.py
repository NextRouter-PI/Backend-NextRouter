"""Construção do snapshot congelado de configuração de um dia de atendimento."""

from datetime import datetime, timedelta

from django.db.models import Prefetch
from django.utils import timezone

from modules.transport.models import RecurringService, RecurringServiceStop


def point_data(point) -> dict:
    if point is None:
        return {}
    return {
        field: getattr(point, field)
        for field in ('street', 'number', 'complement', 'neighborhood', 'city', 'state', 'cep', 'latitude', 'longitude')
    }


def instant(date, clock, days_before: int = 0) -> datetime:
    return timezone.make_aware(datetime.combine(date - timedelta(days=days_before), clock))


def service_data(service: RecurringService, group) -> dict:
    origin = service.origin or (service.vehicle.garage_point if service.vehicle_id else None)
    destination = service.destination or (
        group.destination
        if service.direction == 'outbound'
        else (service.vehicle.garage_point if service.vehicle_id else None)
    )
    prefetched_stops = getattr(service, '_prefetched_configured_stops', None)
    stops = (
        prefetched_stops
        if prefetched_stops is not None
        else service.configured_stops.select_related('point').order_by('position')
    )
    return {
        'id': service.pk,
        'direction': service.direction,
        'target_time': service.target_time.isoformat(),
        'duration': service.planned_duration.total_seconds() if service.planned_duration else None,
        'turnaround': service.turnaround_duration.total_seconds() if service.turnaround_duration is not None else None,
        'driver_id': service.driver_membership.driver_id
        if service.driver_membership_id and service.driver_membership.status == 'active'
        else None,
        'driver_membership_id': service.driver_membership_id,
        'vehicle_id': service.vehicle_id,
        'origin': point_data(origin),
        'destination': point_data(destination),
        'common': point_data(group.destination),
        'stops': [point_data(stop.point) for stop in stops],
    }


def active_services_for_date(group, date) -> list[RecurringService]:
    stops_qs = RecurringServiceStop.objects.select_related('point').order_by('position')
    queryset = (
        RecurringService.objects
        .for_group(group)
        .valid_on(date)
        .select_related('driver_membership', 'vehicle__garage_point', 'origin', 'destination')
        .prefetch_related(Prefetch('configured_stops', queryset=stops_qs, to_attr='_prefetched_configured_stops'))
        .order_by('pk')
    )
    weekday_bit = 1 << date.weekday()
    return [service for service in queryset if service.weekdays & weekday_bit]


def build_day_configuration(group, services: list[RecurringService], *, existing=None) -> dict:
    previous = existing.configuration_snapshot if existing else {}
    return {
        'services': [service_data(service, group) for service in services],
        'issues': [],
        'eligibility_versions': [],
        'closed_revision': previous.get('closed_revision'),
        'operational_issue': previous.get('operational_issue'),
        'maintenance_attempted_at': previous.get('maintenance_attempted_at'),
    }
