import logging
from datetime import timedelta
from math import isfinite

from django.db import transaction
from django.utils import timezone

from modules.accounts.models import User
from modules.organizations.models import Passenger
from modules.transport.models import RouteOptimizationJob, Travel
from modules.transport.osrm import OSRMError, optimize_coordinates
from shared.geocoding import GeocodingError, geocode_address

logger = logging.getLogger(__name__)


def resolve_waypoint(data):
    if 'latitude' in data and 'longitude' in data and data['latitude'] is not None and data['longitude'] is not None:
        latitude, longitude = float(data['latitude']), float(data['longitude'])
    else:
        latitude, longitude = geocode_address(
            street=data.get('street', ''),
            number=data.get('number', ''),
            neighborhood=data.get('neighborhood', ''),
            city=data.get('city', ''),
            state=data.get('state', ''),
            cep=data.get('cep', ''),
            strict=True,
        )
    if not (isfinite(latitude) and isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise GeocodingError('Endereço sem coordenadas válidas.')
    return [longitude, latitude]


def process_optimization(job):
    path = job.path
    if Travel.objects.filter(path=path, status=Travel.Status.IN_PROGRESS).exists():
        raise OSRMError('Aguarde a viagem em andamento terminar antes de alterar a rota.', status_code=400)

    start_payload = dict(job.start or {})
    explicit_stops = start_payload.pop('_stops', None) or []
    has_fixed_end = bool(job.end)

    passengers = {
        passenger.pk: passenger
        for passenger in Passenger.objects.select_related('user').filter(
            pk__in=job.passenger_ids, route_group=path.route_group, is_approved=True
        )
    }
    if len(passengers) != len(job.passenger_ids):
        raise GeocodingError('Um participante não pertence mais a este grupo de rota.')

    selected_ids = sorted(job.passenger_ids)
    coordinates = [resolve_waypoint(start_payload)]
    stop_metadata = []

    for passenger_id in selected_ids:
        user = passengers[passenger_id].user
        if user.latitude is None or user.longitude is None:
            if not all((user.street, user.number, user.city, user.cep)):
                raise GeocodingError('Falta endereço completo de um participante.')
            latitude, longitude = geocode_address(
                street=user.street,
                number=user.number,
                neighborhood=user.neighborhood,
                city=user.city,
                state=user.state,
                cep=user.cep,
                strict=True,
            )
            updated = User.objects.filter(
                pk=user.pk, street=user.street, number=user.number, city=user.city, cep=user.cep
            ).update(latitude=latitude, longitude=longitude, geocoded_at=timezone.now())
            if not updated:
                raise GeocodingError('Endereço alterado durante a otimização. Solicite novamente.')
            user.latitude, user.longitude = latitude, longitude
        lon_lat = resolve_waypoint({'latitude': user.latitude, 'longitude': user.longitude})
        coordinates.append(lon_lat)
        stop_metadata.append({
            'user_id': str(user.pk),
            'longitude': lon_lat[0],
            'latitude': lon_lat[1],
        })

    for stop in explicit_stops:
        lon_lat = resolve_waypoint(stop)
        coordinates.append(lon_lat)
        entry = {'longitude': lon_lat[0], 'latitude': lon_lat[1]}
        if stop.get('label'):
            entry['label'] = stop['label']
        stop_metadata.append(entry)

    if has_fixed_end:
        coordinates.append(resolve_waypoint(job.end))

    result = optimize_coordinates(coordinates, has_fixed_end=has_fixed_end)
    stop_indices = result['order'][1:-1] if has_fixed_end else result['order'][1:]

    with transaction.atomic():
        path = type(path).objects.select_for_update().get(pk=path.pk)
        if path.optimization_jobs.order_by('-pk').values_list('pk', flat=True).first() != job.pk:
            job.status = RouteOptimizationJob.Status.FAILED
            job.error = 'Substituído por uma solicitação mais recente.'
            job.save(update_fields=['status', 'error', 'updated_at'])
            return None
        if Travel.objects.filter(path=path, status=Travel.Status.IN_PROGRESS).exists():
            raise OSRMError(
                'A viagem começou durante a otimização. Solicite novamente após seu término.', status_code=400
            )
        path.points = [stop_metadata[index - 1] for index in stop_indices]
        path.start_point = {'longitude': coordinates[0][0], 'latitude': coordinates[0][1]}
        path.end_point = {'longitude': coordinates[-1][0], 'latitude': coordinates[-1][1]} if has_fixed_end else None
        path.distance_meters = result['distance_meters']
        path.duration_seconds = result['duration_seconds']
        path.geometry = result['geometry']
        path.optimized_at = timezone.now()
        path.is_outdated = False
        path.save(
            update_fields=[
                'points',
                'start_point',
                'end_point',
                'distance_meters',
                'duration_seconds',
                'geometry',
                'optimized_at',
                'is_outdated',
            ]
        )
        job.status = RouteOptimizationJob.Status.DONE
        job.passenger_ids, job.start, job.end, job.error = [], {}, {}, ''
        job.save(update_fields=['status', 'passenger_ids', 'start', 'end', 'error', 'updated_at'])
        logger.info('route_optimized path_id=%s job_id=%s', path.pk, job.pk)
    return result


def claim_job():
    with transaction.atomic():
        now = timezone.now()
        stale = RouteOptimizationJob.objects.filter(
            status=RouteOptimizationJob.Status.RUNNING, updated_at__lt=now - timedelta(minutes=5)
        )
        stale.filter(attempts__gte=3).update(status=RouteOptimizationJob.Status.FAILED, error='Tempo limite excedido.')
        stale.filter(attempts__lt=3).update(status=RouteOptimizationJob.Status.PENDING, available_at=now)
        jobs = RouteOptimizationJob.objects.filter(
            status=RouteOptimizationJob.Status.PENDING, available_at__lte=now
        ).order_by('pk')
        job = jobs.select_for_update(skip_locked=True).first()
        if job:
            job.status = RouteOptimizationJob.Status.RUNNING
            job.attempts += 1
            job.save(update_fields=['status', 'attempts', 'updated_at'])
        return job
