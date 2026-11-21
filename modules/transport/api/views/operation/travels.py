from rest_framework.response import Response

from modules.transport.access import travels_for
from modules.transport.api.serializers.operation import (
    InvitationSerializer,
    InviteInput,
    LocationSerializer,
    PublicationSerializer,
    SnapshotSerializer,
    TravelSerializer,
    VehicleAssignmentInput,
)
from modules.transport.models import Travel
from modules.transport.services.execution import cancel_travel, finish_travel, start_travel
from modules.transport.services.invitations import invite_driver, report_unavailability
from modules.transport.services.planning import assign_vehicle, calculate_travel, publish_travel
from modules.transport.services.tracking import read_location
from shared.api import EmptyInput, OperationInput, RevisionInput
from shared.domain_api import DomainViewSet, domain_action, domain_resource


@domain_resource('Viagens', 'viagens datadas')
class TravelViewSet(DomainViewSet):
    queryset = Travel.objects.none()
    serializer_class = TravelSerializer
    filterset_fields = ('company', 'service_day', 'service', 'service_day__date', 'status', 'driver', 'vehicle')

    def get_scoped_queryset(self, user):
        return travels_for(user).select_related('service_day', 'service').order_by('-service_day__date', 'pk')

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
        return self.respond(finish_travel(actor_id=request.user.pk, travel_id=self.get_object().pk))

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

    @domain_action(
        'Consulte a última posição autorizada',
        methods=('get',),
        response=LocationSerializer,
        description=(
            'Somente operação ativa e participação vigente. '
            'Posição ausente/desatualizada é explícita; não expõe outros passageiros.'
        ),
    )
    def location(self, request, pk=None):
        return Response(read_location(actor_id=request.user.pk, travel_id=self.get_object().pk))
