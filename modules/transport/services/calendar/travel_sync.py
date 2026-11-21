"""Sincronização das viagens planejadas de um dia de atendimento."""

from datetime import datetime, timedelta

from modules.transport.models import Travel

from .snapshot_builder import instant


def sync_day_travels(day, group, date, configuration: dict, *, previous_snapshot: dict | None) -> None:
    """Garante 1 viagem por serviço elegível e invalida viagens afetadas por mudança de snapshot."""
    existing_by_service = {travel.service_id: travel for travel in day.travels.all()}
    eligible_services = {data['id'] for data in configuration['services']}

    # Registra pendências de serviços removidos antes de comparar o snapshot completo.
    for service_id, travel in sorted(existing_by_service.items(), key=lambda pair: pair[1].pk):
        if service_id not in eligible_services and travel.status != Travel.Status.CANCELED:
            configuration['issues'].append(f'travel:{travel.pk}:service_removed')

    invalidate_changed = previous_snapshot is not None and previous_snapshot != configuration

    for data in configuration['services']:
        target = instant(date, datetime.fromisoformat(f'2000-01-01T{data["target_time"]}').time())
        duration = timedelta(seconds=data['duration']) if data['duration'] is not None else timedelta(minutes=60)
        start, end = (target - duration, target) if data['direction'] == 'outbound' else (target, target + duration)

        travel = existing_by_service.get(data['id'])
        if travel is None:
            travel = Travel.objects.create(
                service_day=day,
                service_id=data['id'],
                company=group.company,
                planned_start=start,
                planned_end=end,
                driver_id=data['driver_id'],
                vehicle_id=data['vehicle_id'],
            )
            existing_by_service[data['id']] = travel
            continue

        if travel.status == Travel.Status.CANCELED:
            continue
        if invalidate_changed:
            travel.invalidate()
            travel.planned_start = start
            travel.planned_end = end
            travel.driver_id = data['driver_id']
            travel.vehicle_id = data['vehicle_id']
            travel.save(update_fields=['planned_start', 'planned_end', 'driver', 'vehicle'])
