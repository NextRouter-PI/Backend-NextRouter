"""Guards de transporte registrados nos módulos `accounts` e `organizations` via `TransportConfig.ready()`."""

from django.db.models import Q

from modules.accounts.services import deactivate_account, guard_account_deactivation
from modules.organizations.services.moderation import review_company
from modules.transport.models import Travel
from shared.exceptions import require

__all__ = [
    'deactivate_account',
    'guard_account_deactivation',
    'guard_company_moderation_in_transport',
    'guard_transport_deactivation',
    'review_company',
]


def guard_transport_deactivation(user_id):
    active = Travel.objects.filter(status='in_progress', service_day__isnull=False).filter(
        Q(company__user_id=user_id)
        | Q(driver__user_id=user_id)
        | Q(
            participations__eligibility__passenger__user_id=user_id,
            participations__status__in=['allocated', 'on_board'],
        )
    )
    require(
        not active.exists(),
        'operation_in_progress',
        'Não desative a conta durante participação operacional em andamento.',
    )


def guard_company_moderation_in_transport(company, approve: bool):
    if not approve:
        require(
            not company.travels.filter(status='in_progress').exists(),
            'operation_in_progress',
            'Não desaprove a empresa durante viagem em andamento.',
        )
