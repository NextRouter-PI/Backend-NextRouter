"""Atribuição e troca de grupo de rota para vínculos ativos de passageiros."""

from django.db import transaction
from django.utils import timezone

from modules.organizations.hooks import (
    clone_group_service_authorizations,
    emit_membership_notification,
    notify_route_group_changed,
)
from modules.organizations.models import CompanyRouteGroup, OperationalPoint, PassengerGroupMembership

from .errors import MembershipError
from .locking import get_or_membership_error, lock_membership_context, require_actor, require_approved_company
from .participation import ensure_profile_can_change


@transaction.atomic
def assign_passenger_group(*, actor_id, membership_id, route_group_id, transport_point_id=None):
    """Empresa atribui/troca grupo; guarda cada intervalo e não transfere alocações."""
    ctx = lock_membership_context(membership_id, actor_id=actor_id)
    membership, profile, company, users = ctx.membership, ctx.profile, ctx.company, ctx.users
    require_actor(actor_id, company.user_id)
    require_approved_company(company, users)
    if membership.status != 'active' or membership.passenger_id is None:
        raise MembershipError('Selecione vínculo ativo de passageiro.', code='invalid_passenger_membership')
    if not users[profile.user_id].is_active:
        raise MembershipError('O titular precisa estar ativo.', code='profile_unavailable')
    group = get_or_membership_error(
        CompanyRouteGroup.objects.select_for_update().filter(company=company), pk=route_group_id
    )
    point = None
    if transport_point_id is not None:
        point = get_or_membership_error(
            OperationalPoint.objects.select_for_update().filter(company=company), pk=transport_point_id
        )
    current = membership.passenger_group_memberships.select_for_update().filter(ended_at=None).order_by('pk').first()
    if current and current.route_group_id == group.pk and current.transport_point_id == transport_point_id:
        return current
    now = timezone.now()
    ensure_profile_can_change(profile, now=now)
    if now < membership.reviewed_at or (current and now < current.started_at):
        raise MembershipError('A alteração antecede o início do vínculo/grupo.', code='invalid_time')
    if current:
        current.ended_at = now
        current.ended_by_id = actor_id
        current.save(update_fields=['ended_at', 'ended_by'])
    result = PassengerGroupMembership.objects.create(
        membership=membership,
        route_group=group,
        transport_point=point,
        assigned_by_id=actor_id,
        started_at=now,
    )
    # Mudança somente do ponto preserva as escolhas humanas de serviço no mesmo grupo.
    # Troca de grupo exige novas autorizações explícitas, sem inferi-las por horário.
    if current and current.route_group_id == group.pk:
        clone_group_service_authorizations(source_participation=current, target_participation=result, group=group)
    emit_membership_notification(
        recipient_id=profile.user_id,
        membership_id=membership.pk,
        deduplication_key=f'membership:{membership.pk}:group:{result.pk}',
        status='active',
        occurred_at=now,
    )
    affected = {group.pk: group}
    if current:
        affected[current.route_group_id] = current.route_group
    for affected_group in sorted(affected.values(), key=lambda item: item.pk):
        notify_route_group_changed(affected_group)
    return result
