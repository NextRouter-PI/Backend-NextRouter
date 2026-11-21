"""Vínculos empresariais, sem espelhar flags/grupos ou enviar e-mail legado.

Ordem de locks deste recorte: empresa, perfil estável, vínculo, usuários por PK.
API e ações do admin usam este caminho; identidade não guarda flags empresariais.
"""

from django.db import transaction
from django.utils import timezone

from modules.organizations.hooks import emit_membership_notification, notify_route_group_changed
from modules.organizations.models import (
    Company,
    CompanyMembership,
    CompanyRouteGroup,
    MembershipEvent,
    Passenger,
    PassengerGroupMembership,
)

from .errors import MembershipError
from .locking import (
    get_or_membership_error,
    lock_membership_context,
    lock_profile,
    lock_users,
    require_actor,
    require_approved_company,
    validate_reason,
)
from .participation import ensure_profile_can_change


def _record(membership: CompanyMembership, *, actor_id, action, recipient_id, occurred_at, reason=''):
    MembershipEvent.objects.create(
        membership=membership, action=action, actor_id=actor_id, occurred_at=occurred_at, reason=reason
    )
    emit_membership_notification(
        recipient_id=recipient_id,
        membership_id=membership.pk,
        deduplication_key=f'membership:{membership.pk}:{action}',
        status=membership.status,
        occurred_at=occurred_at,
    )


@transaction.atomic
def request_membership(
    *, actor_id, company_id, passenger_id=None, driver_id=None, route_group_id=None, contact_phone=''
):
    """Titular solicita; repetição enquanto pendente na mesma empresa é idempotente."""
    company = get_or_membership_error(Company.objects.select_for_update(), pk=company_id)
    profile = lock_profile(passenger_id=passenger_id, driver_id=driver_id)
    profile_field = 'passenger_id' if isinstance(profile, Passenger) else 'driver_id'
    requested_group = None
    if route_group_id is not None and isinstance(profile, Passenger):
        requested_group = get_or_membership_error(CompanyRouteGroup.objects.filter(company=company), pk=route_group_id)
    clean_phone = ''.join(ch for ch in str(contact_phone or '') if ch.isdigit())[:20]
    current = (
        CompanyMembership.objects
        .select_for_update()
        .filter(**{profile_field: profile.pk})
        .open()
        .order_by('pk')
        .first()
    )
    users = lock_users(actor_id=actor_id, profile=profile, company=company)
    require_actor(actor_id, profile.user_id)
    require_approved_company(company, users)
    resolved_phone = clean_phone or (users[profile.user_id].phone or '')[:20]
    if current:
        if current.status == CompanyMembership.Status.PENDING and current.company_id == company.pk:
            updated_fields = []
            if requested_group and current.requested_route_group_id != requested_group.pk:
                current.requested_route_group = requested_group
                updated_fields.append('requested_route_group')
            if resolved_phone and current.contact_phone != resolved_phone:
                current.contact_phone = resolved_phone
                updated_fields.append('contact_phone')
            if updated_fields:
                current.save(update_fields=updated_fields)
            return current
        raise MembershipError('O perfil já possui pedido pendente ou vínculo ativo.', code='membership_open')
    now = timezone.now()
    membership = CompanyMembership.objects.create(
        company=company,
        **{profile_field: profile.pk},
        requested_route_group=requested_group,
        contact_phone=resolved_phone,
        requested_by_id=actor_id,
        created_at=now,
    )
    _record(
        membership,
        actor_id=actor_id,
        action=MembershipEvent.Action.REQUESTED,
        recipient_id=company.user_id,
        occurred_at=now,
    )
    return membership


def _decide(*, actor_id, membership_id, status, action, reason):
    reason = validate_reason(reason)
    ctx = lock_membership_context(membership_id, actor_id=actor_id)
    membership, profile, company, users = ctx.membership, ctx.profile, ctx.company, ctx.users
    require_actor(actor_id, company.user_id)
    require_approved_company(company, users)
    if membership.status == status:
        return membership
    if membership.status != CompanyMembership.Status.PENDING:
        raise MembershipError('O pedido não está pendente.', code='membership_not_pending')
    if status == CompanyMembership.Status.ACTIVE and not users[profile.user_id].is_active:
        raise MembershipError('O titular precisa estar ativo.', code='profile_unavailable')
    now = timezone.now()
    if now < membership.created_at:
        raise MembershipError('O instante da decisão antecede a solicitação.', code='invalid_time')
    membership.transition_decision(target_status=status, actor_id=actor_id, now=now)
    _record(membership, actor_id=actor_id, action=action, recipient_id=profile.user_id, occurred_at=now, reason=reason)
    return membership


@transaction.atomic
def end_membership(*, actor_id, membership_id, reason=''):
    """Encerra sem apagar identidade/história; operação/futuro precisam estar resolvidos."""
    reason = validate_reason(reason)
    ctx = lock_membership_context(membership_id, actor_id=actor_id)
    membership, profile, company = ctx.membership, ctx.profile, ctx.company
    if actor_id not in (profile.user_id, company.user_id):
        raise MembershipError('Ator não autorizado.', code='permission_denied')
    if membership.status == CompanyMembership.Status.ENDED:
        return membership
    if membership.status != CompanyMembership.Status.ACTIVE:
        raise MembershipError('O vínculo não está ativo.', code='membership_not_active')
    now = timezone.now()
    ensure_profile_can_change(profile, now=now)
    groups = list(membership.passenger_group_memberships.select_for_update().filter(ended_at=None).order_by('pk'))
    if now < membership.reviewed_at or any(now < group.started_at for group in groups):
        raise MembershipError('O encerramento antecede o início do vínculo/grupo.', code='invalid_time')
    for group in groups:
        group.ended_at = now
        group.ended_by_id = actor_id
        group.save(update_fields=['ended_at', 'ended_by'])
    membership.transition_end(actor_id=actor_id, now=now)
    _record(
        membership,
        actor_id=actor_id,
        action=MembershipEvent.Action.ENDED,
        recipient_id=company.user_id if actor_id == profile.user_id else profile.user_id,
        occurred_at=now,
        reason=reason,
    )
    for group in groups:
        notify_route_group_changed(group.route_group)
    return membership


@transaction.atomic
def approve_membership(*, actor_id, membership_id, reason=''):
    """Empresa titular aprova; se passageiro solicitou um grupo de rota, adiciona automaticamente ao grupo."""
    membership = _decide(
        actor_id=actor_id,
        membership_id=membership_id,
        status=CompanyMembership.Status.ACTIVE,
        action=MembershipEvent.Action.APPROVED,
        reason=reason,
    )
    if (
        membership.passenger_id is not None
        and membership.requested_route_group_id is not None
        and not membership.passenger_group_memberships.filter(ended_at__isnull=True).exists()
    ):
        group = CompanyRouteGroup.objects.filter(
            pk=membership.requested_route_group_id,
            company_id=membership.company_id,
        ).first()
        if group is not None:
            PassengerGroupMembership.objects.create(
                membership=membership,
                route_group=group,
                transport_point=None,
                assigned_by_id=actor_id,
                started_at=membership.reviewed_at or timezone.now(),
            )
            notify_route_group_changed(group)
    return membership


@transaction.atomic
def reject_membership(*, actor_id, membership_id, reason=''):
    return _decide(
        actor_id=actor_id,
        membership_id=membership_id,
        status=CompanyMembership.Status.REJECTED,
        action=MembershipEvent.Action.REJECTED,
        reason=reason,
    )


@transaction.atomic
def withdraw_membership(*, actor_id, membership_id, reason=''):
    """Titular retira pedido mesmo se a empresa deixou de estar aprovada."""
    reason = validate_reason(reason)
    ctx = lock_membership_context(membership_id, actor_id=actor_id)
    membership, profile, company = ctx.membership, ctx.profile, ctx.company
    require_actor(actor_id, profile.user_id)
    if membership.status == CompanyMembership.Status.WITHDRAWN:
        return membership
    if membership.status != CompanyMembership.Status.PENDING:
        raise MembershipError('O pedido não está pendente.', code='membership_not_pending')
    now = timezone.now()
    if now < membership.created_at:
        raise MembershipError('O instante da retirada antecede a solicitação.', code='invalid_time')
    membership.transition_withdraw(actor_id=actor_id, now=now)
    _record(
        membership,
        actor_id=actor_id,
        action=MembershipEvent.Action.WITHDRAWN,
        recipient_id=company.user_id,
        occurred_at=now,
        reason=reason,
    )
    return membership
