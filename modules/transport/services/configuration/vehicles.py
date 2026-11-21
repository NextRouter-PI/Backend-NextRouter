"""Configuração de veículos da frota."""

from django.db import transaction

from modules.organizations.models import OperationalPoint
from modules.transport.models import Travel, Vehicle
from modules.transport.services.actors import company_actor
from modules.transport.services.calendar import regenerate_future_days
from modules.transport.services.locking import lock_company
from shared.exceptions import get, require

VEHICLE_ALLOWED_FIELDS = frozenset({
    'plate',
    'model',
    'year',
    'capacity',
    'status',
    'garage_point_id',
    'color',
    'features',
})


@transaction.atomic
def configure_vehicle(*, actor_id, company_id, vehicle_id=None, **values):
    company = lock_company(company_id)
    company_actor(company, actor_id)
    require(not values.keys() - VEHICLE_ALLOWED_FIELDS, 'protected_field', 'Campo de frota não permitido.')
    vehicle = get(Vehicle.objects.filter(company=company), pk=vehicle_id) if vehicle_id else Vehicle(company=company)
    if vehicle.pk:
        require(
            not vehicle.travels.filter(status=Travel.Status.IN_PROGRESS).exists(),
            'operation_in_progress',
            'Veículo em operação.',
        )
    if values.get('garage_point_id') is not None:
        garage_point = get(OperationalPoint.objects.filter(company=company), pk=values['garage_point_id'])
        require(
            garage_point.point_type == OperationalPoint.PointType.GARAGE,
            'invalid_point_type',
            'O ponto selecionado para o veículo deve ser do tipo garagem.',
        )
    for field, value in values.items():
        setattr(vehicle, field, value)
    vehicle.full_clean()
    vehicle.save()
    for group in company.route_groups.order_by('pk'):
        regenerate_future_days(group)
    for travel in vehicle.travels.dated().filter(status=Travel.Status.SCHEDULED).order_by('pk'):
        travel.invalidate()
    return vehicle
