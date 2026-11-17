from django.shortcuts import get_object_or_404

from modules.organizations.models import CompanyRouteGroup, OperationalPoint
from modules.transport.access import companies_for
from modules.transport.api.serializers.configuration import (
    AutomationInput,
    AutomationSerializer,
    CancelDateInput,
    GenerateInput,
    GroupInput,
    GroupSerializer,
    PointInput,
    PointSerializer,
    PolicyInput,
    PolicySerializer,
    ServiceInput,
    ServiceSerializer,
    StopsInput,
    VehicleInput,
    VehicleSerializer,
)
from modules.transport.api.serializers.daily import CancelDaySerializer, DaySerializer
from modules.transport.models import AutomationSchedule, RecurringService, ResponsePolicy, Vehicle
from modules.transport.services.automation import configure_automation
from modules.transport.services.calendar import generate_horizon
from modules.transport.services.configuration import (
    configure_group,
    configure_point,
    configure_policy,
    configure_service,
    configure_stops,
    configure_vehicle,
)
from modules.transport.services.execution import cancel_date
from shared.domain_api import DomainViewSet, domain_action, domain_resource


class ConfigurationViewSet(DomainViewSet):
    company_lookup = 'company'

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        return self.queryset.model.objects.filter(**{
            f'{self.company_lookup}__in': companies_for(self.request.user)
        }).order_by('pk')

    def own_company(self):
        return get_object_or_404(companies_for(self.request.user))


@domain_resource('Configuração', 'pontos operacionais')
class PointViewSet(ConfigurationViewSet):
    queryset = OperationalPoint.objects.none()
    serializer_class = PointSerializer
    write_serializer_class = PointInput
    filterset_fields = ('company', 'city', 'state')

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


@domain_resource('Configuração', 'grupos de atendimento')
class GroupViewSet(ConfigurationViewSet):
    queryset = CompanyRouteGroup.objects.none()
    serializer_class = GroupSerializer
    write_serializer_class = GroupInput
    filterset_fields = ('company',)

    def create(self, request):
        return self.respond(
            configure_group(actor_id=request.user.pk, company_id=self.own_company().pk, **self.input(GroupInput)),
            status=201,
        )

    def partial_update(self, request, pk=None):
        group = self.get_object()
        data = {'name': group.name, 'destination_id': group.destination_id, **self.input(GroupInput, partial=True)}
        return self.respond(
            configure_group(actor_id=request.user.pk, company_id=group.company_id, group_id=group.pk, **data)
        )

    @domain_action('Configure a política do grupo', request=PolicyInput, response=PolicySerializer)
    def policy(self, request, pk=None):
        return self.respond(
            configure_policy(actor_id=request.user.pk, group_id=self.get_object().pk, **self.input(PolicyInput)),
            PolicySerializer,
        )

    @domain_action('Configure a agenda automática opt-in', request=AutomationInput, response=AutomationSerializer)
    def automation(self, request, pk=None):
        return self.respond(
            configure_automation(
                actor_id=request.user.pk, group_id=self.get_object().pk, **self.input(AutomationInput)
            ),
            AutomationSerializer,
        )

    @domain_action(
        'Consulte o progresso da agenda automática',
        methods=['get'],
        response=AutomationSerializer,
        url_path='automation-status',
    )
    def automation_status(self, request, pk=None):
        schedule = get_object_or_404(AutomationSchedule, route_group=self.get_object())
        return self.respond(schedule, AutomationSerializer)

    @domain_action(
        'Gere um horizonte explícito de atendimentos', request=GenerateInput, response=DaySerializer(many=True)
    )
    def generate(self, request, pk=None):
        days = generate_horizon(actor_id=request.user.pk, group_id=self.get_object().pk, **self.input(GenerateInput))
        return self.respond(days, DaySerializer, many=True)

    @domain_action(
        'Cancele uma data mesmo antes de gerar viagens',
        request=CancelDateInput,
        response=CancelDaySerializer,
        url_path='cancel-date',
    )
    def cancel_date(self, request, pk=None):
        result = cancel_date(actor_id=request.user.pk, group_id=self.get_object().pk, **self.input(CancelDateInput))
        return self.respond(result, CancelDaySerializer)


@domain_resource('Configuração', 'políticas de resposta')
class PolicyViewSet(ConfigurationViewSet):
    company_lookup = 'route_group__company'
    queryset = ResponsePolicy.objects.none()
    serializer_class = PolicySerializer
    filterset_fields = ('route_group',)


@domain_resource('Configuração', 'serviços habituais')
class ServiceViewSet(ConfigurationViewSet):
    company_lookup = 'route_group__company'
    queryset = RecurringService.objects.none()
    serializer_class = ServiceSerializer
    write_serializer_class = ServiceInput
    filterset_fields = ('route_group', 'direction')

    def get_queryset(self):
        return super().get_queryset().prefetch_related('configured_stops')

    def create(self, request):
        data = self.input(ServiceInput)
        group = get_object_or_404(
            CompanyRouteGroup, pk=data.pop('route_group_id'), company__in=companies_for(request.user)
        )
        return self.respond(configure_service(actor_id=request.user.pk, group_id=group.pk, **data), status=201)

    def partial_update(self, request, pk=None):
        service = self.get_object()
        data = self.input(ServiceInput, partial=True)
        if data.pop('route_group_id', service.route_group_id) != service.route_group_id:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({'route_group_id': 'O grupo do serviço não pode ser alterado.'})
        return self.respond(
            configure_service(actor_id=request.user.pk, group_id=service.route_group_id, service_id=service.pk, **data)
        )

    @domain_action('Configure as paradas habituais', request=StopsInput, response=ServiceSerializer)
    def stops(self, request, pk=None):
        service = self.get_object()
        configure_stops(actor_id=request.user.pk, service_id=service.pk, **self.input(StopsInput))
        service.refresh_from_db()
        return self.respond(service)


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
