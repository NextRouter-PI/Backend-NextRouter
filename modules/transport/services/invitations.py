from datetime import datetime

from django.db import transaction
from django.utils import timezone

from modules.organizations.models import CompanyMembership
from modules.transport.models import DriverInvitation, Notification

from .common import active_actor, company_actor, editable, get, invalidate, lock_travel, notify, require


@transaction.atomic
def report_unavailability(*, actor_id, travel_id, operation_id):
    company, travel = lock_travel(travel_id)
    active_actor(actor_id)
    key = f'unavailable:{travel.pk}:{actor_id}:{operation_id}'
    if Notification.objects.filter(recipient_id=company.user_id, deduplication_key=key).exists():
        return travel
    editable(travel)
    require(
        travel.driver_id is not None and travel.driver.user_id == actor_id,
        'permission_denied',
        'Somente o motorista designado informa indisponibilidade.',
    )
    travel.driver_invitations.filter(is_current=True).update(is_current=False)
    invalidate(travel)
    travel.driver = None
    travel.save(update_fields=['driver'])
    notify(
        recipients=[company.user_id],
        kind='invitation',
        resource_type='travel',
        resource_id=travel.pk,
        key=key,
        status='pending',
    )
    return travel


@transaction.atomic
def invite_driver(*, actor_id, travel_id, driver_membership_id, expires_at):
    company, travel = lock_travel(travel_id)
    company_actor(company, actor_id)
    editable(travel)
    membership = get(
        CompanyMembership.objects.filter(company=company, driver__isnull=False, status='active'),
        pk=driver_membership_id,
    )
    require(membership.driver.user.is_active, 'driver_unavailable', 'O motorista está indisponível.')
    now = timezone.now()
    require(
        isinstance(expires_at, datetime) and timezone.is_aware(expires_at) and now < expires_at,
        'invalid_expiry',
        'O prazo deve ser um instante futuro com fuso horário.',
    )
    current = travel.driver_invitations.filter(is_current=True).first()
    if current and current.driver_membership_id == membership.pk and current.expires_at == expires_at:
        return current
    if current:
        current.is_current = False
        if current.status == 'pending':
            current.status, current.closed_at = 'revoked', now
        current.save(update_fields=['is_current', 'status', 'closed_at'])
    invitation = DriverInvitation.objects.create(
        travel=travel, driver_membership=membership, invited_by_id=actor_id, created_at=now, expires_at=expires_at
    )
    invalidate(travel)
    travel.driver = None
    travel.save(update_fields=['driver'])
    notify(
        recipients=[membership.driver.user_id],
        kind='invitation',
        resource_type='invitation',
        resource_id=invitation.pk,
        key=f'invitation:{invitation.pk}:pending',
        status='pending',
    )
    return invitation


@transaction.atomic
def respond_invitation(*, actor_id, invitation_id, accept):
    initial = get(DriverInvitation.objects.all(), pk=invitation_id)
    company, travel = lock_travel(initial.travel_id)
    active_actor(actor_id)
    invitation = get(DriverInvitation.objects.select_for_update(), pk=invitation_id)
    require(
        invitation.driver_membership.driver.user_id == actor_id,
        'permission_denied',
        'Somente o convidado pode responder.',
    )
    require(isinstance(accept, bool), 'invalid_response', 'Aceite inválido.')
    require(invitation.is_current, 'invitation_not_current', 'O convite foi substituído.')
    status = 'accepted' if accept else 'declined'
    if invitation.status == status:
        return invitation
    editable(travel)
    now = timezone.now()
    require(
        invitation.status == 'pending' and now < invitation.expires_at,
        'invitation_expired',
        'O convite não está mais pendente dentro do prazo.',
    )
    require(
        company.is_approved and company.user.is_active and invitation.driver_membership.status == 'active',
        'membership_unavailable',
        'O vínculo/empresa não está apto.',
    )
    invitation.status, invitation.responded_by_id = status, actor_id
    invitation.responded_at = invitation.closed_at = now
    invitation.save(update_fields=['status', 'responded_by', 'responded_at', 'closed_at'])
    if accept:
        travel.driver_id = invitation.driver_membership.driver_id
        travel.save(update_fields=['driver'])
        invalidate(travel)
    notify(
        recipients=[company.user_id],
        kind='invitation',
        resource_type='invitation',
        resource_id=invitation.pk,
        key=f'invitation:{invitation.pk}:{status}',
        status=status,
    )
    return invitation
