from django.shortcuts import get_object_or_404

from modules.organizations.models import CompanyRouteGroup, PassengerGroupMembership
from modules.transport.api.serializers.configuration import (
    AutomationInput,
    AutomationSerializer,
    CancelDateInput,
    GenerateInput,
    GroupInput,
    GroupSerializer,
    GroupUpdateInput,
    PolicyInput,
    PolicySerializer,
    UnassignedPassengerSerializer,
)
from modules.transport.api.serializers.daily import CancelDaySerializer, DaySerializer
from modules.transport.models import AutomationSchedule
from modules.transport.services.automation import configure_automation
from modules.transport.services.calendar import generate_horizon
from modules.transport.services.configuration import configure_group, configure_policy
from modules.transport.services.execution import cancel_date
from shared.domain_api import domain_action, domain_resource

from .base import ConfigurationViewSet


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
        serializer = GroupUpdateInput(data=request.data, partial=True, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        return self.respond(
            configure_group(
                actor_id=request.user.pk,
                company_id=group.company_id,
                group_id=group.pk,
                **serializer.to_service_kwargs(group),
            )
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

    @domain_action(
        'Passageiros vinculados ao grupo ainda sem rota habitual',
        methods=['get'],
        response=UnassignedPassengerSerializer(many=True),
        url_path='unassigned-passengers',
    )
    def unassigned_passengers(self, request, pk=None):
        members = PassengerGroupMembership.objects.unassigned_in_group(self.get_object())
        rows = [UnassignedPassengerSerializer.from_group_membership(gm, request) for gm in members]
        return self.respond(rows, UnassignedPassengerSerializer, many=True)
