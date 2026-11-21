from django.shortcuts import get_object_or_404

from modules.organizations.access import companies_for
from modules.organizations.models import CompanyRouteGroup
from modules.transport.api.serializers.configuration import (
    ServiceInput,
    ServiceSerializer,
    ServiceUpdateInput,
    StopsInput,
)
from modules.transport.models import RecurringService
from modules.transport.services.configuration import configure_service, configure_stops
from shared.domain_api import domain_action, domain_resource

from .base import ConfigurationViewSet


@domain_resource('Configuração', 'serviços habituais')
class ServiceViewSet(ConfigurationViewSet):
    company_lookup = 'route_group__company'
    queryset = RecurringService.objects.none()
    serializer_class = ServiceSerializer
    write_serializer_class = ServiceInput
    filterset_fields = ('route_group', 'direction')

    def get_scoped_queryset(self, user):
        return super().get_scoped_queryset(user).prefetch_related('configured_stops')

    def create(self, request):
        data = self.input(ServiceInput)
        group = get_object_or_404(
            CompanyRouteGroup, pk=data.pop('route_group_id'), company__in=companies_for(request.user)
        )
        return self.respond(configure_service(actor_id=request.user.pk, group_id=group.pk, **data), status=201)

    def partial_update(self, request, pk=None):
        service = self.get_object()
        serializer = ServiceUpdateInput(
            data=request.data,
            partial=True,
            context={**self.get_serializer_context(), 'service': service},
        )
        serializer.is_valid(raise_exception=True)
        return self.respond(
            configure_service(
                actor_id=request.user.pk,
                group_id=service.route_group_id,
                service_id=service.pk,
                **serializer.validated_data,
            )
        )

    @domain_action('Configure as paradas habituais', request=StopsInput, response=ServiceSerializer)
    def stops(self, request, pk=None):
        service = self.get_object()
        configure_stops(actor_id=request.user.pk, service_id=service.pk, **self.input(StopsInput))
        refreshed = self.get_queryset().get(pk=service.pk)
        return self.respond(refreshed)
