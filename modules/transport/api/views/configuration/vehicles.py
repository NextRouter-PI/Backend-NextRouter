from modules.transport.api.serializers.configuration import VehicleInput, VehicleSerializer
from modules.transport.models import Vehicle
from modules.transport.services.configuration import configure_vehicle
from shared.domain_api import domain_resource

from .base import ConfigurationViewSet


@domain_resource('Configuração', 'veículos empresariais')
class VehicleViewSet(ConfigurationViewSet):
    queryset = Vehicle.objects.none()
    serializer_class = VehicleSerializer
    write_serializer_class = VehicleInput
    filterset_fields = ('company', 'status')

    def create(self, request):
        return self.respond(
            configure_vehicle(actor_id=request.user.pk, company_id=self.own_company().pk, **self.input(VehicleInput)),
            status=201,
        )

    def partial_update(self, request, pk=None):
        vehicle = self.get_object()
        return self.respond(
            configure_vehicle(
                actor_id=request.user.pk,
                company_id=vehicle.company_id,
                vehicle_id=vehicle.pk,
                **self.input(VehicleInput, partial=True),
            )
        )
