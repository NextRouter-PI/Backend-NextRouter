from django.db import transaction
from django.utils import timezone

from modules.organizations.models import CompanyRouteGroup, OperationalPoint, PassengerGroupMembership
from modules.transport.models import Notification, PassengerServiceAuthorization

from .errors import MembershipError
from .memberships import _approved_company, _authorize, _get, _locked_membership, _users
from .participation import ensure_profile_can_change


@transaction.atomic
def assign_passenger_group(*, actor_id, membership_id, route_group_id, transport_point_id=None):
    """Empresa atribui/troca grupo; guarda cada intervalo e não transfere alocações."""
    membership, profile, company = _locked_membership(membership_id)
    users = _users(actor_id=actor_id, profile=profile, company=company)
    _authorize(actor_id, company.user_id)
    _approved_company(company, users)
    if membership.status != 'active' or membership.passenger_id is None:
        raise MembershipError('Selecione vínculo ativo de passageiro.', code='invalid_passenger_membership')
    if not users[profile.user_id].is_active:
        raise MembershipError('O titular precisa estar ativo.', code='profile_unavailable')
    group = _get(CompanyRouteGroup.objects.select_for_update().filter(company=company), pk=route_group_id)
    point = None
    if transport_point_id is not None:
        point = _get(OperationalPoint.objects.select_for_update().filter(company=company), pk=transport_point_id)
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
        authorizations = list(current.service_authorizations.select_related('service').order_by('pk'))
        if any(
            authorization.service.route_group_id != group.pk
            or authorization.direction != authorization.service.direction
            or (authorization.is_habitual and authorization.direction != 'outbound')
            for authorization in authorizations
        ):
            raise MembershipError('As autorizações habituais são inconsistentes.', code='invalid_authorization')
        PassengerServiceAuthorization.objects.bulk_create([
            PassengerServiceAuthorization(
                participation=result,
                service_id=authorization.service_id,
                direction=authorization.direction,
                is_habitual=authorization.is_habitual,
            )
            for authorization in authorizations
        ])
    Notification.objects.create(
        recipient_id=profile.user_id,
        kind='membership',
        resource_type='membership',
        resource_id=str(membership.pk),
        deduplication_key=f'membership:{membership.pk}:group:{result.pk}',
        payload={'status': 'active'},
        created_at=now,
    )
    from modules.transport.services.calendar import regenerate_future_days

    affected = {group.pk: group}
    if current:
        affected[current.route_group_id] = current.route_group
    for affected_group in sorted(affected.values(), key=lambda item: item.pk):
        regenerate_future_days(affected_group)
    return result
