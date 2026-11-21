from modules.transport.api.serializers.operation import (
    CorrectionInput,
    EventSerializer,
    ParticipantSerializer,
    PresenceInput,
)
from modules.transport.models import ParticipationEvent, TravelParticipation
from modules.transport.services.execution import correct_participation, record_participation
from shared.domain_api import DomainViewSet, domain_action, domain_resource


@domain_resource('Execução', 'participações em viagens')
class ParticipantViewSet(DomainViewSet):
    queryset = TravelParticipation.objects.none()
    serializer_class = ParticipantSerializer
    filterset_fields = ('travel', 'eligibility', 'leg', 'status')

    def get_scoped_queryset(self, user):
        return (
            TravelParticipation.objects
            .visible_to(user)
            .select_related(
                'travel__company',
                'travel__driver',
                'eligibility__passenger__user__profile_picture',
            )
            .order_by('pk')
        )

    @domain_action('Registre embarque ausência ou desembarque', request=PresenceInput, response=EventSerializer)
    def record(self, request, pk=None):
        return self.respond(
            record_participation(
                actor_id=request.user.pk, participation_id=self.get_object().pk, **self.input(PresenceInput)
            ),
            EventSerializer,
        )

    @domain_action('Corrija presença com motivo e referência', request=CorrectionInput, response=EventSerializer)
    def correct(self, request, pk=None):
        return self.respond(
            correct_participation(
                actor_id=request.user.pk, participation_id=self.get_object().pk, **self.input(CorrectionInput)
            ),
            EventSerializer,
        )


@domain_resource('Execução', 'eventos de participação')
class EventViewSet(DomainViewSet):
    queryset = ParticipationEvent.objects.none()
    serializer_class = EventSerializer
    filterset_fields = ('participation', 'kind')

    def get_scoped_queryset(self, user):
        return ParticipationEvent.objects.filter(
            participation__in=TravelParticipation.objects.visible_to(user)
        ).order_by('pk')
