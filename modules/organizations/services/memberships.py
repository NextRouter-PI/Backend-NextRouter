"""Vínculos novos, sem espelhar flags/grupos ou enviar e-mail legado.

Ordem de locks deste recorte: empresa, perfil estável, vínculo, usuários por PK.
Todas as operações disputam o perfil, mesmo quando ainda não existe um ciclo.
Nenhum caller operacional deve usar estes serviços antes da substituição coordenada.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from modules.organizations.models import Company, CompanyMembership, Driver, MembershipEvent, Passenger
from modules.transport.models import Notification

from .errors import MembershipError


def _get(queryset, **lookup):
    try:
        return queryset.get(**lookup)
    except queryset.model.DoesNotExist as exc:
        raise MembershipError('Recurso não encontrado.', code='not_found') from exc


def _profile(*, passenger_id, driver_id):
    if (passenger_id is None) == (driver_id is None):
        raise MembershipError('Informe exatamente um perfil.', code='invalid_profile')
    model, pk = (Passenger, passenger_id) if passenger_id is not None else (Driver, driver_id)
    return _get(model.objects.select_for_update(), pk=pk)


def _users(*, actor_id, profile, company):
    users = {
        user.pk: user
        for user in get_user_model()
        .objects.select_for_update()
        .filter(pk__in=[actor_id, profile.user_id, company.user_id])
        .order_by('pk')
    }
    actor = users.get(actor_id)
    if actor is None or not actor.is_active:
        raise MembershipError('Ator não autorizado.', code='permission_denied')
    return users


def _approved_company(company, users):
    if not company.is_approved or company.is_rejected or not users[company.user_id].is_active:
        raise MembershipError('A empresa precisa estar aprovada e ativa.', code='company_unavailable')


def _authorize(actor_id, expected_id):
    if actor_id != expected_id:
        raise MembershipError('Ator não autorizado.', code='permission_denied')


def _reason(reason):
    if not isinstance(reason, str) or len(reason) > 500:
        raise MembershipError('O motivo deve ter até 500 caracteres.', code='invalid_reason')
    return reason.strip()


def _record(membership, *, actor_id, action, recipient_id, occurred_at, reason=''):
    MembershipEvent.objects.create(
        membership=membership, action=action, actor_id=actor_id, occurred_at=occurred_at, reason=reason
    )
    Notification.objects.create(
        recipient_id=recipient_id,
        kind='membership',
        resource_type='membership',
        resource_id=str(membership.pk),
        deduplication_key=f'membership:{membership.pk}:{action}',
        payload={'status': membership.status},
        created_at=occurred_at,
    )


@transaction.atomic
def request_membership(*, actor_id, company_id, passenger_id=None, driver_id=None):
    """Titular solicita; repetição enquanto pendente na mesma empresa é idempotente."""
    company = _get(Company.objects.select_for_update(), pk=company_id)
    profile = _profile(passenger_id=passenger_id, driver_id=driver_id)
    profile_field = 'passenger_id' if isinstance(profile, Passenger) else 'driver_id'
    current = (
        CompanyMembership.objects
        .select_for_update()
        .filter(**{profile_field: profile.pk}, status__in=['pending', 'active'])
        .order_by('pk')
        .first()
    )
    users = _users(actor_id=actor_id, profile=profile, company=company)
    _authorize(actor_id, profile.user_id)
    _approved_company(company, users)
    if current:
        if current.status == CompanyMembership.Status.PENDING and current.company_id == company.pk:
            return current
        raise MembershipError('O perfil já possui pedido pendente ou vínculo ativo.', code='membership_open')
    now = timezone.now()
    membership = CompanyMembership.objects.create(
        company=company, **{profile_field: profile.pk}, requested_by_id=actor_id, created_at=now
    )
    _record(
        membership,
        actor_id=actor_id,
        action=MembershipEvent.Action.REQUESTED,
        recipient_id=company.user_id,
        occurred_at=now,
    )
    return membership


def _locked_membership(membership_id):
    # A leitura inicial só localiza o agregado; ownership/estado vêm da releitura sob lock.
    initial = _get(CompanyMembership.objects.all(), pk=membership_id)
    company = _get(Company.objects.select_for_update(), pk=initial.company_id)
    profile = _profile(passenger_id=initial.passenger_id, driver_id=initial.driver_id)
    membership = _get(CompanyMembership.objects.select_for_update(), pk=membership_id)
    if (membership.passenger_id, membership.driver_id, membership.company_id) != (
        initial.passenger_id,
        initial.driver_id,
        initial.company_id,
    ):
        raise MembershipError('O vínculo foi alterado; repita a operação.', code='membership_changed')
    return membership, profile, company


def _decide(*, actor_id, membership_id, status, action, reason):
    reason = _reason(reason)
    membership, profile, company = _locked_membership(membership_id)
    users = _users(actor_id=actor_id, profile=profile, company=company)
    _authorize(actor_id, company.user_id)
    _approved_company(company, users)
    if membership.status == status:
        return membership
    if membership.status != CompanyMembership.Status.PENDING:
        raise MembershipError('O pedido não está pendente.', code='membership_not_pending')
    if status == CompanyMembership.Status.ACTIVE and not users[profile.user_id].is_active:
        raise MembershipError('O titular precisa estar ativo.', code='profile_unavailable')
    now = timezone.now()
    if now < membership.created_at:
        raise MembershipError('O instante da decisão antecede a solicitação.', code='invalid_time')
    membership.status = status
    membership.reviewed_by_id = actor_id
    membership.reviewed_at = now
    membership.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    _record(membership, actor_id=actor_id, action=action, recipient_id=profile.user_id, occurred_at=now, reason=reason)
    return membership


@transaction.atomic
def end_membership(*, actor_id, membership_id, reason=''):
    """Encerra sem apagar identidade/história; operação/futuro precisam estar resolvidos."""
    from .participation import ensure_profile_can_change

    reason = _reason(reason)
    membership, profile, company = _locked_membership(membership_id)
    _users(actor_id=actor_id, profile=profile, company=company)
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
    membership.status = CompanyMembership.Status.ENDED
    membership.ended_at = now
    membership.ended_by_id = actor_id
    membership.save(update_fields=['status', 'ended_at', 'ended_by'])
    _record(
        membership,
        actor_id=actor_id,
        action=MembershipEvent.Action.ENDED,
        recipient_id=company.user_id if actor_id == profile.user_id else profile.user_id,
        occurred_at=now,
        reason=reason,
    )
    return membership


@transaction.atomic
def approve_membership(*, actor_id, membership_id, reason=''):
    """Empresa titular aprova sem exigir grupo e sem publicar/alocar viagens."""
    return _decide(
        actor_id=actor_id,
        membership_id=membership_id,
        status=CompanyMembership.Status.ACTIVE,
        action=MembershipEvent.Action.APPROVED,
        reason=reason,
    )


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
    reason = _reason(reason)
    membership, profile, company = _locked_membership(membership_id)
    _users(actor_id=actor_id, profile=profile, company=company)
    _authorize(actor_id, profile.user_id)
    if membership.status == CompanyMembership.Status.WITHDRAWN:
        return membership
    if membership.status != CompanyMembership.Status.PENDING:
        raise MembershipError('O pedido não está pendente.', code='membership_not_pending')
    now = timezone.now()
    if now < membership.created_at:
        raise MembershipError('O instante da retirada antecede a solicitação.', code='invalid_time')
    membership.status = CompanyMembership.Status.WITHDRAWN
    membership.withdrawn_by_id = actor_id
    membership.withdrawn_at = now
    membership.save(update_fields=['status', 'withdrawn_by', 'withdrawn_at'])
    _record(
        membership,
        actor_id=actor_id,
        action=MembershipEvent.Action.WITHDRAWN,
        recipient_id=company.user_id,
        occurred_at=now,
        reason=reason,
    )
    return membership
