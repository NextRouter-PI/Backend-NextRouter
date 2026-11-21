"""Infraestrutura de domínio: mutex empresarial, autorização e avisos mínimos.

Toda escrita nova toma primeiro Company. Dentro da empresa, isso serializa geração,
respostas, configuração, capacidade, execução e encerramento de vínculo. Nunca tomar
um lock de job antes de Company. Operações entre viagens usam PK crescente.
"""

from django.contrib.auth import get_user_model
from django.utils import timezone

from modules.organizations.models import Company, CompanyMembership
from modules.transport.models import Notification, Travel
from shared.exceptions import DomainError, get, require

__all__ = [
    'DomainError',
    'active_actor',
    'company_actor',
    'current_time',
    'editable',
    'get',
    'invalidate',
    'lock_company',
    'lock_travel',
    'membership_for',
    'notify',
    'require',
    'travel_recipients',
]


def lock_company(company_id):
    return get(Company.objects.select_for_update(), pk=company_id)


def active_actor(actor_id):
    return get(get_user_model().objects.filter(is_active=True), pk=actor_id)


def company_actor(company, actor_id):
    active_actor(actor_id)
    require(actor_id == company.user_id, 'permission_denied', 'Somente a empresa titular pode executar esta ação.')
    require(
        company.is_approved and not company.is_rejected,
        'company_unavailable',
        'A empresa precisa estar aprovada.',
    )


def lock_travel(travel_id):
    initial = get(Travel.objects.filter(service_day__isnull=False), pk=travel_id)
    company = lock_company(initial.company_id)
    travel = get(Travel.objects.select_for_update().filter(company=company, service_day__isnull=False), pk=travel_id)
    return company, travel


def membership_for(company, *, passenger_id=None, driver_id=None):
    filters = {'passenger_id': passenger_id} if passenger_id is not None else {'driver_id': driver_id}
    return get(CompanyMembership.objects.filter(company=company, status='active'), **filters)


def editable(travel):
    travel.ensure_editable()


def notify(*, recipients, kind, resource_type, resource_id, key, status, revision=None):
    return Notification.objects.emit_bulk(
        recipients=recipients,
        kind=kind,
        resource_type=resource_type,
        resource_id=resource_id,
        key=key,
        status=status,
        revision=revision,
    )


def travel_recipients(travel):
    return travel.recipient_user_ids()


def invalidate(travel):
    travel.invalidate()


def current_time():
    return timezone.now()
