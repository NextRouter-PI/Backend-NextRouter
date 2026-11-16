from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.organizations.models import Company
from modules.transport.models import Travel

from .common import active_actor, get, lock_company, require


def _user_companies(user_id):
    return (
        Company.objects
        .filter(
            Q(user_id=user_id) | Q(memberships__passenger__user_id=user_id) | Q(memberships__driver__user_id=user_id)
        )
        .order_by('pk')
        .values_list('pk', flat=True)
        .distinct()
    )


@transaction.atomic
def guard_account_deactivation(*, user_id):
    # Empresas antes de usuários; início também bloqueia usuários da lista antes de gravar.
    for company_id in list(_user_companies(user_id)):
        lock_company(company_id)
    users = list(
        get_user_model()
        .objects.select_for_update()
        .filter(Q(pk=user_id) | Q(is_staff=True, is_active=True))
        .order_by('pk')
    )
    require(any(user.pk == user_id for user in users), 'not_found', 'Conta não encontrada.')
    target = next(user for user in users if user.pk == user_id)
    require(
        not (target.is_staff and target.is_active) or sum(user.is_staff and user.is_active for user in users) > 1,
        'last_staff',
        'Não é possível desativar o último administrador ativo.',
    )
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


@transaction.atomic
def deactivate_account(*, actor_id, user_id):
    actor = active_actor(actor_id)
    require(actor_id == user_id or actor.is_staff, 'permission_denied', 'Desativação não autorizada.')
    guard_account_deactivation(user_id=user_id)
    user = get(get_user_model().objects.all(), pk=user_id)
    if user.is_staff:
        count = get_user_model().objects.filter(is_staff=True, is_active=True).count()
        require(count > 1 or not user.is_active, 'last_staff', 'Não é possível desativar o último administrador ativo.')
    user.is_active = False
    user.save(update_fields=['is_active'])
    from modules.accounts.services import revoke_sessions

    revoke_sessions(user)
    return user


@transaction.atomic
def review_company(*, actor_id, company_id, approve):
    company = lock_company(company_id)
    actor = active_actor(actor_id)
    require(
        actor.is_staff and isinstance(approve, bool), 'permission_denied', 'Somente moderador pode revisar a empresa.'
    )
    if not approve:
        require(
            not company.travels.filter(status='in_progress').exists(),
            'operation_in_progress',
            'Não desaprove a empresa durante viagem em andamento.',
        )
    company.is_approved, company.is_rejected = approve, not approve
    company.reviewed_by_id, company.reviewed_at = actor_id, timezone.now()
    company.save(update_fields=['is_approved', 'is_rejected', 'reviewed_by', 'reviewed_at'])
    return company
