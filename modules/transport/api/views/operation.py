from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from modules.transport.access import companies_for, eligibilities_for, operational_travels_for, travels_for
from modules.transport.api.serializers.operation import (
    CorrectionInput,
    EventSerializer,
    InvitationSerializer,
    InviteInput,
    InviteResponseInput,
    JobSerializer,
    LocationSerializer,
    NotificationSerializer,
    ParticipantSerializer,
    PresenceInput,
    PublicationSerializer,
    SnapshotSerializer,
    StopInput,
    StopSerializer,
    TravelSerializer,
    VehicleAssignmentInput,
)
from modules.transport.models import (
    DriverInvitation,
    Notification,
    ParticipationEvent,
    RouteOptimizationJob,
    RouteSnapshot,
    RouteStop,
    Travel,
    TravelParticipation,
    TravelPublication,
)
from modules.transport.services.execution import (
    cancel_travel,
    correct_participation,
    finish_travel,
    handle_stop,
    record_participation,
    start_travel,
)
from modules.transport.services.invitations import invite_driver, report_unavailability, respond_invitation
from modules.transport.services.maintenance import read_notification
from modules.transport.services.planning import assign_vehicle, calculate_travel, publish_travel
from modules.transport.services.tracking import read_location
from shared.api import EmptyInput, OperationInput, RevisionInput
from shared.domain_api import ERRORS, DomainViewSet, domain_action, domain_resource


@domain_resource('Viagens', 'viagens datadas')
class TravelViewSet(DomainViewSet):
    queryset = Travel.objects.none()
    serializer_class = TravelSerializer
    filterset_fields = ('company', 'service_day', 'service', 'service_day__date', 'status', 'driver', 'vehicle')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return (
            travels_for(self.request.user).select_related('service_day', 'service').order_by('-service_day__date', 'pk')
        )

    @domain_action(
        'Enfileire o cálculo da revisão atual', request=RevisionInput, response=SnapshotSerializer, status=202
    )
    def calculate(self, request, pk=None):
        return self.respond(
            calculate_travel(actor_id=request.user.pk, travel_id=self.get_object().pk, **self.input(RevisionInput)),
            SnapshotSerializer,
            status=202,
        )

    @domain_action('Publique a viagem pronta', request=RevisionInput, response=PublicationSerializer)
    def publish(self, request, pk=None):
        return self.respond(
            publish_travel(actor_id=request.user.pk, travel_id=self.get_object().pk, **self.input(RevisionInput)),
            PublicationSerializer,
        )

    @domain_action('Inicie a viagem designada', request=RevisionInput, response=TravelSerializer)
    def start(self, request, pk=None):
        return self.respond(
            start_travel(actor_id=request.user.pk, travel_id=self.get_object().pk, **self.input(RevisionInput))
        )

    @domain_action('Finalize a viagem sem presenças pendentes', response=TravelSerializer)
    def finish(self, request, pk=None):
        self.input(EmptyInput)
        travel = finish_travel(actor_id=request.user.pk, travel_id=self.get_object().pk)
        return self.respond(travel)

    @domain_action('Cancele a viagem antes do início', response=TravelSerializer)
    def cancel(self, request, pk=None):
        self.input(EmptyInput)
        return self.respond(cancel_travel(actor_id=request.user.pk, travel_id=self.get_object().pk))

    @domain_action(
        'Informe sua indisponibilidade', request=OperationInput, response=TravelSerializer, url_path='unavailability'
    )
    def unavailability(self, request, pk=None):
        return self.respond(
            report_unavailability(
                actor_id=request.user.pk, travel_id=self.get_object().pk, **self.input(OperationInput)
            )
        )

    @domain_action(
        'Convide substituto escolhido pela empresa',
        request=InviteInput,
        response=InvitationSerializer,
        url_path='invite-driver',
    )
    def invite_driver(self, request, pk=None):
        return self.respond(
            invite_driver(actor_id=request.user.pk, travel_id=self.get_object().pk, **self.input(InviteInput)),
            InvitationSerializer,
        )

    @domain_action(
        'Designe outro veículo da empresa',
        request=VehicleAssignmentInput,
        response=TravelSerializer,
        url_path='assign-vehicle',
    )
    def assign_vehicle(self, request, pk=None):
        return self.respond(
            assign_vehicle(
                actor_id=request.user.pk, travel_id=self.get_object().pk, **self.input(VehicleAssignmentInput)
            )
        )

    @extend_schema(
        summary='Consulte a última posição autorizada',
        description='Somente operação ativa e participação '
        'vigente. Posição ausente/desatualizada é explícita; não expõe outros passageiros.',
        responses={200: LocationSerializer, **ERRORS},
    )
    @action(detail=True, methods=['get'])
    def location(self, request, pk=None):
        return Response(read_location(actor_id=request.user.pk, travel_id=self.get_object().pk))


def participations_for(user):
    return (
        TravelParticipation.objects
        .filter(
            Q(travel__in=operational_travels_for(user))
            | Q(eligibility__in=eligibilities_for(user).filter(passenger__user=user))
        )
        .filter(travel__in=travels_for(user))
        .distinct()
    )


@domain_resource('Execução', 'participações em viagens')
class ParticipantViewSet(DomainViewSet):
    queryset = TravelParticipation.objects.none()
    serializer_class = ParticipantSerializer
    filterset_fields = ('travel', 'eligibility', 'leg', 'status')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return participations_for(self.request.user).select_related('eligibility__passenger__user').order_by('pk')

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

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return ParticipationEvent.objects.filter(participation__in=participations_for(self.request.user)).order_by('pk')


@domain_resource('Percursos', 'snapshots de percursos')
class SnapshotViewSet(DomainViewSet):
    queryset = RouteSnapshot.objects.none()
    serializer_class = SnapshotSerializer
    filterset_fields = ('travel', 'state', 'change_request')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return RouteSnapshot.objects.filter(travel__in=operational_travels_for(self.request.user)).order_by('-pk')


@domain_resource('Percursos', 'publicações de viagens')
class PublicationViewSet(DomainViewSet):
    queryset = TravelPublication.objects.none()
    serializer_class = PublicationSerializer
    filterset_fields = ('travel', 'revision')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return TravelPublication.objects.filter(travel__in=travels_for(self.request.user)).order_by('-pk')


@domain_resource('Execução', 'paradas do percurso')
class StopViewSet(DomainViewSet):
    queryset = RouteStop.objects.none()
    serializer_class = StopSerializer
    filterset_fields = ('snapshot', 'state')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return (
            RouteStop.objects
            .filter(snapshot__travel__in=operational_travels_for(self.request.user))
            .prefetch_related('participants')
            .order_by('snapshot', 'position')
        )

    @domain_action('Avance a parada na ordem do percurso', request=StopInput, response=StopSerializer)
    def handle(self, request, pk=None):
        return self.respond(
            handle_stop(actor_id=request.user.pk, stop_id=self.get_object().pk, **self.input(StopInput))
        )


@domain_resource('Convites', 'convites de motorista')
class InvitationViewSet(DomainViewSet):
    queryset = DriverInvitation.objects.none()
    serializer_class = InvitationSerializer
    filterset_fields = ('travel', 'status', 'is_current')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        user = self.request.user
        return (
            DriverInvitation.objects
            .filter(
                Q(travel__company__in=companies_for(user))
                | Q(
                    driver_membership__driver__user=user,
                    driver_membership__status='active',
                    travel__company__is_approved=True,
                    travel__company__user__is_active=True,
                )
            )
            .select_related('travel')
            .distinct()
            .order_by('-pk')
        )

    @domain_action(
        'Aceite ou recuse seu convite vigente',
        request=InviteResponseInput,
        response=InvitationSerializer,
        url_path='respond',
    )
    def reply(self, request, pk=None):
        invitation = respond_invitation(
            actor_id=request.user.pk, invitation_id=self.get_object().pk, **self.input(InviteResponseInput)
        )
        return self.respond(invitation)


@domain_resource('Avisos', 'avisos persistentes')
class NotificationViewSet(DomainViewSet):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    filterset_fields = ('kind', 'resource_type')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at', '-pk')

    @domain_action('Marque seu aviso como lido', response=NotificationSerializer)
    def read(self, request, pk=None):
        self.input(EmptyInput)
        return self.respond(read_notification(actor_id=request.user.pk, notification_id=self.get_object().pk))


@domain_resource('Percursos', 'estado dos trabalhos de cálculo')
class JobViewSet(DomainViewSet):
    queryset = RouteOptimizationJob.objects.none()
    serializer_class = JobSerializer
    filterset_fields = ('snapshot', 'status')

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return RouteOptimizationJob.objects.filter(
            snapshot__travel__company__in=companies_for(self.request.user), snapshot__isnull=False
        ).order_by('-pk')
