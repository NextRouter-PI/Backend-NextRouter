"""Governança de contas (desativação com guards registrados por outros módulos)."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from modules.accounts.hooks import run_deactivation_guards, run_deactivation_pre_locks
from shared.exceptions import get_or_not_found, require

from .sessions import revoke_sessions


@transaction.atomic
def guard_account_deactivation(*, user_id):
    # Ordem de locks preservada: empresas (via pre_lock) antes de usuários.
    run_deactivation_pre_locks(user_id)
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
    run_deactivation_guards(user_id)
    return target


@transaction.atomic
def deactivate_account(*, actor_id, user_id):
    user_model = get_user_model()
    actor = get_or_not_found(user_model.objects.active(), pk=actor_id)
    require(actor_id == user_id or actor.is_staff, 'permission_denied', 'Desativação não autorizada.')
    user = guard_account_deactivation(user_id=user_id)
    user.deactivate()
    revoke_sessions(user)
    return user
