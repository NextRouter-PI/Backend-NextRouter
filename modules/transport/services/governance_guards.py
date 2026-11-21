"""Guards e listeners de transporte registrados em `accounts` e `organizations` via `TransportConfig.ready()`."""

from django.db.models import Q
from django.utils import timezone

from modules.organizations.models import Passenger
from modules.organizations.services.errors import MembershipError
from modules.transport.models import Travel, TravelParticipation
from shared.exceptions import require


def guard_transport_deactivation(user_id):
    active = Travel.objects.filter(status=Travel.Status.IN_PROGRESS, service_day__isnull=False).filter(
        Q(company__user_id=user_id)
        | Q(driver__user_id=user_id)
        | Q(
            participations__eligibility__passenger__user_id=user_id,
            participations__status__in=[
                TravelParticipation.Status.ALLOCATED,
                TravelParticipation.Status.ON_BOARD,
            ],
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
            not company.travels.filter(status=Travel.Status.IN_PROGRESS).exists(),
            'operation_in_progress',
            'Não desaprove a empresa durante viagem em andamento.',
        )


def guard_profile_can_change_in_transport(profile, now):
    """Bloqueia encerramento/troca de grupo se houver viagem em andamento ou alocação/designação futura."""
    travels = Travel.objects.dated()
    if isinstance(profile, Passenger):
        participations = TravelParticipation.objects.active_occupancy().filter(eligibility__passenger_id=profile.pk)
        travels = travels.filter(pk__in=participations.values('travel_id'))
    else:
        travels = travels.filter(driver_id=profile.pk)
    # Viagem em andamento bloqueia mesmo se começou num dia anterior.
    if travels.filter(status=Travel.Status.IN_PROGRESS).exists():
        raise MembershipError('O perfil participa de viagem em andamento.', code='operation_in_progress')
    if (
        travels
        .filter(status=Travel.Status.SCHEDULED)
        .filter(Q(service_day__date__gte=timezone.localdate(now)) | Q(planned_end__gte=now))
        .exists()
    ):
        raise MembershipError('Resolva as alocações/designações futuras antes de alterar.', code='future_allocation')
