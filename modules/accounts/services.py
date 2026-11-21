import logging

from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q

from modules.accounts.hooks import run_deactivation_guards, run_deactivation_pre_locks
from shared.exceptions import get_or_not_found, require

logger = logging.getLogger(__name__)


def revoke_sessions(user):
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    user.sessions.filter(is_active=True).update(is_active=False)
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


def revoke_session(session):
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    token = OutstandingToken.objects.filter(jti=session.refresh_jti).first()
    if token:
        BlacklistedToken.objects.get_or_create(token=token)
    session.is_active = False
    session.save(update_fields=['is_active'])


def send_email_token(email, code, subject):
    body = (
        'Olá!\n\n'
        f'Seu código de verificação do NextRouter é: {code}\n\n'
        'O código é válido por 15 minutos. Se você não solicitou este código, ignore este e-mail.\n'
    )
    message = EmailMessage(subject=subject, body=body, to=[email])
    try:
        message.send()
        return True
    except Exception as exc:
        logger.warning('email_token_delivery_failed reason=%s', type(exc).__name__)
        return False


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
    actor = get_or_not_found(user_model.objects.filter(is_active=True), pk=actor_id)
    require(actor_id == user_id or actor.is_staff, 'permission_denied', 'Desativação não autorizada.')
    user = guard_account_deactivation(user_id=user_id)
    user.deactivate()
    revoke_sessions(user)
    return user
