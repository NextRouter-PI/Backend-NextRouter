"""Barreira compartilhada para encerramento e mudança de grupo do domínio novo."""

from django.db.models import Q
from django.utils import timezone

from modules.organizations.models import Passenger
from modules.transport.models import Travel, TravelParticipation

from .errors import MembershipError


def ensure_profile_can_change(profile, *, now):
    """Chamador já bloqueou empresa/perfil; futuras escritas operacionais devem fazê-lo.

    Não usa confirmação legada como prova de alocação/embarque. Não modifica viagens,
    respostas ou reservas. A mesma ordem empresa→perfil será exigida dos novos callers.
    """
    travels = Travel.objects.filter(service_day__isnull=False)
    if isinstance(profile, Passenger):
        participations = TravelParticipation.objects.filter(
            eligibility__passenger_id=profile.pk, status__in=['allocated', 'on_board']
        )
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
