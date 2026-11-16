"""Infraestrutura de domínio: mutex empresarial, autorização e avisos mínimos.

Toda escrita nova toma primeiro Company. Dentro da empresa, isso serializa geração,
respostas, configuração, capacidade, execução e encerramento de vínculo. Nunca tomar
um lock de job antes de Company. Operações entre viagens usam PK crescente.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.organizations.models import Company, CompanyMembership
from modules.transport.models import Notification, Travel


class DomainError(ValidationError):
    """Erro com código estável, sem dependência de HTTP."""


def require(condition, code, message):
    if not condition:
        raise DomainError(message, code=code)


def get(queryset, **lookup):
    try:
        return queryset.get(**lookup)
    except queryset.model.DoesNotExist as exc:
        raise DomainError('Recurso não encontrado.', code='not_found') from exc


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
    require(travel.status == 'scheduled', 'travel_not_scheduled', 'A viagem não pode mais ser alterada.')
    require(not travel.service_day.canceled_at, 'day_canceled', 'O atendimento está cancelado.')


def notify(*, recipients, kind, resource_type, resource_id, key, status, revision=None):
    payload = {'status': status}
    if revision is not None:
        payload['revision'] = revision
    for recipient_id in sorted(set(recipients), key=str):
        Notification.objects.get_or_create(
            recipient_id=recipient_id,
            deduplication_key=key,
            defaults={
                'kind': kind,
                'resource_type': resource_type,
                'resource_id': str(resource_id),
                'payload': payload,
                'created_at': timezone.now(),
            },
        )


def travel_recipients(travel):
    recipients = [travel.company.user_id]
    if travel.driver_id:
        recipients.append(travel.driver.user_id)
    recipients.extend(travel.participations.values_list('eligibility__passenger__user_id', flat=True))
    return recipients


def invalidate(travel):
    editable(travel)
    travel.revision = max([travel.revision, *travel.route_snapshots.values_list('revision', flat=True)]) + 1
    travel.current_snapshot = None
    travel.planning_status = 'draft'
    travel.save(update_fields=['revision', 'current_snapshot', 'planning_status'])


def current_time():
    return timezone.now()
