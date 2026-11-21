"""Autorização de atores operacionais (empresa titular e motorista designado)."""

from django.contrib.auth import get_user_model

from modules.organizations.models import CompanyMembership
from shared.exceptions import get, require


def active_actor(actor_id):
    return get(get_user_model().objects.filter(is_active=True), pk=actor_id)


def membership_for(company, *, passenger_id=None, driver_id=None):
    filters = {'passenger_id': passenger_id} if passenger_id is not None else {'driver_id': driver_id}
    return get(CompanyMembership.objects.filter(company=company, status='active'), **filters)


def company_actor(company, actor_id):
    active_actor(actor_id)
    require(actor_id == company.user_id, 'permission_denied', 'Somente a empresa titular pode executar esta ação.')
    require(
        company.is_approved and not company.is_rejected,
        'company_unavailable',
        'A empresa precisa estar aprovada.',
    )


def driver_actor(travel, actor_id):
    active_actor(actor_id)
    require(
        travel.driver_id is not None and travel.driver.user_id == actor_id,
        'permission_denied',
        'Somente o motorista designado pode executar esta ação.',
    )
    require(
        travel.company.is_operational,
        'company_unavailable',
        'A empresa não está apta a operar.',
    )
    membership_for(travel.company, driver_id=travel.driver_id)
