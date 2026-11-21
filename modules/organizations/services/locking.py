"""Locking determinístico e validações compartilhadas de vínculos empresariais.

Ordem de locks obrigatória: Company → Profile (Passenger/Driver) → CompanyMembership → Users por PK.
"""

from dataclasses import dataclass

from django.contrib.auth import get_user_model

from modules.organizations.models import Company, CompanyMembership, Driver, Passenger

from .errors import MembershipError


@dataclass(frozen=True, slots=True)
class LockedMembershipContext:
    membership: CompanyMembership
    profile: Passenger | Driver
    company: Company
    users: dict


def get_or_membership_error(queryset, **lookup):
    try:
        return queryset.get(**lookup)
    except queryset.model.DoesNotExist as exc:
        raise MembershipError('Recurso não encontrado.', code='not_found') from exc


def lock_profile(*, passenger_id, driver_id) -> Passenger | Driver:
    if (passenger_id is None) == (driver_id is None):
        raise MembershipError('Informe exatamente um perfil.', code='invalid_profile')
    model, pk = (Passenger, passenger_id) if passenger_id is not None else (Driver, driver_id)
    return get_or_membership_error(model.objects.select_for_update(), pk=pk)


def lock_users(*, actor_id, profile, company) -> dict:
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


def lock_membership_context(membership_id, *, actor_id) -> LockedMembershipContext:
    # A leitura inicial só localiza o agregado; ownership/estado vêm da releitura sob lock.
    initial = get_or_membership_error(CompanyMembership.objects.all(), pk=membership_id)
    company = get_or_membership_error(Company.objects.select_for_update(), pk=initial.company_id)
    profile = lock_profile(passenger_id=initial.passenger_id, driver_id=initial.driver_id)
    membership = get_or_membership_error(CompanyMembership.objects.select_for_update(), pk=membership_id)
    if (membership.passenger_id, membership.driver_id, membership.company_id) != (
        initial.passenger_id,
        initial.driver_id,
        initial.company_id,
    ):
        raise MembershipError('O vínculo foi alterado; repita a operação.', code='membership_changed')
    users = lock_users(actor_id=actor_id, profile=profile, company=company)
    return LockedMembershipContext(membership=membership, profile=profile, company=company, users=users)


def require_approved_company(company: Company, users: dict) -> None:
    if not company.is_approved or company.is_rejected or not users[company.user_id].is_active:
        raise MembershipError('A empresa precisa estar aprovada e ativa.', code='company_unavailable')


def require_actor(actor_id, expected_id) -> None:
    if actor_id != expected_id:
        raise MembershipError('Ator não autorizado.', code='permission_denied')


def validate_reason(reason) -> str:
    if not isinstance(reason, str) or len(reason) > 500:
        raise MembershipError('O motivo deve ter até 500 caracteres.', code='invalid_reason')
    return reason.strip()
