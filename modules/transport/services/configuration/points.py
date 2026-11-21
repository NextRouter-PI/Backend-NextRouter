"""Configuração de pontos operacionais."""

from django.db import transaction

from modules.organizations.models import OperationalPoint
from modules.transport.services.actors import company_actor
from modules.transport.services.calendar import regenerate_future_days
from modules.transport.services.locking import lock_company
from shared.exceptions import get, require

POINT_ALLOWED_FIELDS = frozenset({
    'point_type',
    'name',
    'street',
    'number',
    'complement',
    'neighborhood',
    'city',
    'state',
    'cep',
    'latitude',
    'longitude',
})


@transaction.atomic
def configure_point(*, actor_id, company_id, point_id=None, **values):
    company = lock_company(company_id)
    company_actor(company, actor_id)
    require(not values.keys() - POINT_ALLOWED_FIELDS, 'protected_field', 'Campo de ponto não permitido.')
    point = (
        get(OperationalPoint.objects.filter(company=company), pk=point_id)
        if point_id
        else OperationalPoint(company=company, created_by_id=actor_id)
    )
    if point.pk and 'point_type' in values and values['point_type'] != point.point_type:
        new_type = values['point_type']
        if new_type != OperationalPoint.PointType.GARAGE:
            require(
                not point.garaged_vehicles.exists(),
                'invalid_point_type',
                'Este ponto está vinculado como garagem de veículos.',
            )
        if new_type != OperationalPoint.PointType.DESTINATION:
            require(
                not point.destination_groups.exists(),
                'invalid_point_type',
                'Este ponto está vinculado como destino de grupos de atendimento.',
            )
    for field, value in values.items():
        setattr(point, field, value)
    point.full_clean()
    point.save()
    for group in company.route_groups.order_by('pk'):
        regenerate_future_days(group)
    return point
