"""Configuração de grupos de atendimento e políticas de resposta."""

from django.db import transaction

from modules.organizations.models import CompanyRouteGroup, OperationalPoint
from modules.transport.models import ResponsePolicy
from modules.transport.services.actors import company_actor
from modules.transport.services.calendar import regenerate_future_days
from modules.transport.services.locking import group_access, lock_company
from shared.exceptions import get, require

POLICY_ALLOWED_FIELDS = frozenset({
    'opens_days_before',
    'opens_time',
    'normal_days_before',
    'normal_time',
    'extension_days_before',
    'extension_time',
})


@transaction.atomic
def configure_policy(*, actor_id, group_id, **values):
    group = group_access(group_id, actor_id)
    require(not values.keys() - POLICY_ALLOWED_FIELDS, 'protected_field', 'Campo de política não permitido.')
    policy = ResponsePolicy.objects.filter(route_group=group).first() or ResponsePolicy(route_group=group)
    for field, value in values.items():
        setattr(policy, field, value)
    policy.full_clean()
    policy.save()
    # Prazos efetivos de datas existentes são imutáveis; a política vale para novos dias.
    return policy


@transaction.atomic
def configure_group(*, actor_id, company_id, group_id=None, name, destination_id):
    company = lock_company(company_id)
    company_actor(company, actor_id)
    point = get(OperationalPoint.objects.filter(company=company), pk=destination_id)
    require(
        point.point_type == OperationalPoint.PointType.DESTINATION,
        'invalid_point_type',
        'O destino do grupo deve ser um ponto operacional do tipo destino.',
    )
    group = (
        get(CompanyRouteGroup.objects.filter(company=company), pk=group_id)
        if group_id
        else CompanyRouteGroup(company=company)
    )
    group.name, group.destination = name, point
    group.full_clean()
    group.save()
    regenerate_future_days(group)
    return group
