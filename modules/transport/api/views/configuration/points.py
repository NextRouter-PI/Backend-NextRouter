from modules.organizations.models import OperationalPoint
from modules.transport.api.serializers.configuration import PointInput, PointSerializer
from modules.transport.services.configuration import configure_point
from shared.domain_api import domain_resource

from .base import ConfigurationViewSet


@domain_resource('Configuração', 'pontos operacionais')
class PointViewSet(ConfigurationViewSet):
    queryset = OperationalPoint.objects.none()
    serializer_class = PointSerializer
    write_serializer_class = PointInput
    filterset_fields = ('company', 'city', 'state', 'point_type')

    def create(self, request):
        return self.respond(
            configure_point(actor_id=request.user.pk, company_id=self.own_company().pk, **self.input(PointInput)),
            status=201,
        )

    def partial_update(self, request, pk=None):
        point = self.get_object()
        return self.respond(
            configure_point(
                actor_id=request.user.pk,
                company_id=point.company_id,
                point_id=point.pk,
                **self.input(PointInput, partial=True),
            )
        )
