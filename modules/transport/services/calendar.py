import hashlib
import json
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from modules.organizations.models import PassengerGroupMembership
from modules.transport.models import RecurringService, ResponsePolicy, ServiceDay, ServiceDayEligibility, Travel

from .common import get, invalidate, require
from .configuration import group_access


def point_data(point):
    if point is None:
        return {}
    return {
        field: getattr(point, field)
        for field in ('street', 'number', 'complement', 'neighborhood', 'city', 'state', 'cep', 'latitude', 'longitude')
    }


def instant(date, clock, days_before=0):
    return timezone.make_aware(datetime.combine(date - timedelta(days=days_before), clock))


def service_data(service, group):
    origin = service.origin or (service.vehicle.garage_point if service.vehicle_id else None)
    destination = service.destination or (
        group.destination
        if service.direction == 'outbound'
        else (service.vehicle.garage_point if service.vehicle_id else None)
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
        'stops': [
            point_data(stop.point) for stop in service.configured_stops.select_related('point').order_by('position')
        ],
    }


def _generate(group, date, *, explicit=False):
    now = timezone.now()
    require(date >= timezone.localdate(now), 'past_date', 'Não gere atendimentos passados.')
    existing = ServiceDay.objects.filter(route_group=group, date=date).first()
    if existing and (
        existing.canceled_at
        or (
            not explicit
            and (date <= timezone.localdate(now) or existing.travels.filter(published_revision__isnull=False).exists())
        )
        or existing.travels.filter(status__in=['in_progress', 'finished']).exists()
    ):
        return existing
    policy = get(ResponsePolicy.objects.all(), route_group=group) if existing is None else None
    services = [
        s
        for s in RecurringService.objects.filter(route_group=group).order_by('pk')
        if s.valid_from <= date
        and (s.valid_until is None or s.valid_until >= date)
        and s.weekdays & (1 << date.weekday())
    ]
    configuration = {
        'services': [service_data(s, group) for s in services],
        'issues': [],
        'eligibility_versions': [],
        'closed_revision': existing.configuration_snapshot.get('closed_revision') if existing else None,
        'operational_issue': existing.configuration_snapshot.get('operational_issue') if existing else None,
    }
    day = existing or ServiceDay(
        route_group=group,
        date=date,
        opens_at=instant(date, policy.opens_time, policy.opens_days_before),
        normal_deadline=instant(date, policy.normal_time, policy.normal_days_before),
        extension_deadline=(
            instant(date, policy.extension_time, policy.extension_days_before)
            if policy.extension_time is not None
            else None
        ),
    )
    if not existing:
        day.full_clean()
        day.save()
    active_groups = (
        PassengerGroupMembership.objects
        .filter(
            route_group=group, ended_at=None, membership__status='active', membership__passenger__user__is_active=True
        )
        .select_related('membership', 'transport_point')
        .order_by('pk')
    )
    current_passengers = set()
    eligible_services = {s.pk for s in services}
    for participation in active_groups:
        passenger_id = participation.membership.passenger_id
        current_passengers.add(passenger_id)
        authorized = sorted(
            set(participation.service_authorizations.values_list('service_id', flat=True)) & eligible_services
        )
        eligibility, created = ServiceDayEligibility.objects.get_or_create(
            day=day,
            passenger_id=passenger_id,
            defaults={
                'group_membership': participation,
                'authorized_service_ids': authorized,
                'point_snapshot': point_data(participation.transport_point),
            },
        )
        if not created:
            # Não descartar escolhas, alocações ou elegibilidade histórica conflitantes.
            chosen = set(
                eligibility.participations.filter(status__in=['allocated', 'on_board']).values_list(
                    'travel__service_id', flat=True
                )
            )
            response = getattr(eligibility, 'response', None)
            if response:
                chosen.update(
                    getattr(response, f'{leg}_service_id')
                    for leg in ('outbound', 'return')
                    if getattr(response, f'{leg}_service_id') and not getattr(response, f'{leg}_withdrawn_at')
                )
            if chosen - set(authorized):
                configuration['issues'].append(f'eligibility:{eligibility.pk}:unauthorized_choice')
            eligibility.group_membership = participation
            eligibility.authorized_service_ids = authorized
            eligibility.point_snapshot = point_data(participation.transport_point)
            eligibility.save(update_fields=['group_membership', 'authorized_service_ids', 'point_snapshot'])
        fingerprint = hashlib.sha256(
            json.dumps(
                [eligibility.pk, participation.pk, authorized, eligibility.point_snapshot], sort_keys=True
            ).encode()
        ).hexdigest()
        configuration['eligibility_versions'].append(fingerprint)
    for eligibility in day.eligibilities.exclude(passenger_id__in=current_passengers):
        response = getattr(eligibility, 'response', None)
        if eligibility.participations.filter(status__in=['allocated', 'on_board']).exclude(
            travel__status='canceled'
        ).exists() or (
            response
            and any(
                getattr(response, f'{leg}_service_id') and not getattr(response, f'{leg}_withdrawn_at')
                for leg in ('outbound', 'return')
            )
        ):
            configuration['issues'].append(f'eligibility:{eligibility.pk}:membership_changed')
    for data in configuration['services']:
        if data['duration'] is None or data['turnaround'] is None:
            configuration['issues'].append(f'service:{data["id"]}:schedule_incomplete')
            continue
        target = instant(date, datetime.fromisoformat(f'2000-01-01T{data["target_time"]}').time())
        duration = timedelta(seconds=data['duration'])
        start, end = (target - duration, target) if data['direction'] == 'outbound' else (target, target + duration)
        travel, _ = Travel.objects.get_or_create(
            service_day=day,
            service_id=data['id'],
            defaults={
                'company': group.company,
                'planned_start': start,
                'planned_end': end,
                'driver_id': data['driver_id'],
                'vehicle_id': data['vehicle_id'],
            },
        )
        if travel.status == 'canceled':
            continue
        if existing and existing.configuration_snapshot != configuration:
            invalidate(travel)
            travel.planned_start, travel.planned_end = start, end
            travel.driver_id, travel.vehicle_id = data['driver_id'], data['vehicle_id']
            travel.save(update_fields=['planned_start', 'planned_end', 'driver', 'vehicle'])
    for travel in day.travels.exclude(service_id__in=eligible_services).exclude(status='canceled'):
        configuration['issues'].append(f'travel:{travel.pk}:service_removed')
    old = day.configuration_snapshot
    if existing and old != configuration:
        day.revision += 1
    day.configuration_snapshot = configuration
    day.save(update_fields=['configuration_snapshot', 'revision'])
    if configuration['issues']:
        day.travels.filter(status='scheduled').update(planning_status='blocked')
    return day


@transaction.atomic
def generate_day(*, actor_id, group_id, date):
    return _generate(group_access(group_id, actor_id), date)


def regenerate_future_days(group):
    # Chamador já mantém o mutex empresarial. Não reabre datas nem muda prazos efetivos.
    for date in group.days.filter(date__gt=timezone.localdate()).order_by('date').values_list('date', flat=True):
        _generate(group, date)


@transaction.atomic
def revise_day(*, actor_id, day_id, expected_revision):
    initial = get(ServiceDay.objects.all(), pk=day_id)
    group = group_access(initial.route_group_id, actor_id)
    day = get(ServiceDay.objects.filter(route_group=group), pk=day_id)
    require(day.revision == expected_revision, 'stale_revision', 'O atendimento foi alterado.')
    require(
        not day.canceled_at and not day.travels.filter(status__in=['in_progress', 'finished']).exists(),
        'execution_started',
        'A revisão do atendimento exige viagens ainda não iniciadas.',
    )
    return _generate(group, day.date, explicit=True)


@transaction.atomic
def generate_horizon(*, actor_id, group_id, start_date, horizon_days, batch_size):
    require(
        type(horizon_days) is int and horizon_days > 0 and type(batch_size) is int and batch_size > 0,
        'invalid_horizon',
        'Informe horizonte e lote positivos.',
    )
    group = group_access(group_id, actor_id)
    return [_generate(group, start_date + timedelta(days=offset)) for offset in range(min(horizon_days, batch_size))]
