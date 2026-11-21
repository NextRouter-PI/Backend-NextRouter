"""Mutex empresarial e locking em duas fases para o domínio de transporte.

Toda escrita toma primeiro `Company`. Nunca tomar um lock de job antes de `Company`.
"""

from modules.organizations.models import Company, CompanyRouteGroup
from modules.transport.models import Travel
from shared.exceptions import get

from .actors import company_actor


def lock_company(company_id):
    return get(Company.objects.select_for_update(), pk=company_id)


def lock_for_company(queryset, pk, *, company_getter, company_filter=None, select_for_update=True):
    """Executa lock em duas fases: descobre a empresa, trava `Company` e relê o recurso sob lock."""
    initial = get(queryset, pk=pk)
    company = lock_company(company_getter(initial))
    reloaded = queryset.select_for_update(of=('self',)) if select_for_update else queryset
    if company_filter is not None:
        reloaded = reloaded.filter(**{company_filter: company})
    return company, get(reloaded, pk=pk)


def lock_travel(travel_id):
    return lock_for_company(
        Travel.objects.filter(service_day__isnull=False),
        travel_id,
        company_getter=lambda travel: travel.company_id,
        company_filter='company',
    )


def group_access(group_id, actor_id):
    company, group = lock_for_company(
        CompanyRouteGroup.objects.all(),
        group_id,
        company_getter=lambda item: item.company_id,
        company_filter='company',
        select_for_update=False,
    )
    company_actor(company, actor_id)
    return group
