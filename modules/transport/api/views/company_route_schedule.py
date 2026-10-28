from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from modules.organizations.permissions import IsCompany, IsScheduleOwner
from modules.transport.api.serializers.company_route_schedule import (
    CompanyRouteScheduleCreateSerializer,
    CompanyRouteScheduleListAndRetrieveSerializer,
    CompanyRouteSchedulePatchSerializer,
)
from modules.transport.models.company_route_schedule import CompanyRouteSchedule
from shared.openapi import document_viewset


@document_viewset(
    'Horários',
    'horário de rota',
    'horários de rota',
    read='Empresa, motorista e aluno aprovados consultam horários de seus grupos; administrador consulta todos.',
    create='Empresa aprovada cria horário no próprio grupo; ida e volta não podem se sobrepor a outros horários.',
    change='Somente empresa aprovada dona do grupo altera ou exclui horários.',
    read_response=CompanyRouteScheduleListAndRetrieveSerializer,
    create_response=CompanyRouteScheduleCreateSerializer,
    update_response=CompanyRouteSchedulePatchSerializer,
)
class CompanyRouteScheduleViewSet(ModelViewSet):
    queryset = CompanyRouteSchedule.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_fields = ('route_group',)

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsCompany]
        elif self.action in {'partial_update', 'destroy'}:
            permission_classes = [IsAuthenticated, IsCompany, IsScheduleOwner]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyRouteScheduleCreateSerializer
        elif self.action == 'partial_update':
            return CompanyRouteSchedulePatchSerializer
        return CompanyRouteScheduleListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = CompanyRouteSchedule.objects.select_related(
            'route_group',
            'route_group__company',
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return (
            queryset
            .filter(
                Q(route_group__company__user=user, route_group__company__is_approved=True)
                | Q(
                    route_group__drivers__user=user,
                    route_group__drivers__is_approved=True,
                    route_group__company__is_approved=True,
                )
                | Q(
                    route_group__passengers__user=user,
                    route_group__passengers__is_approved=True,
                    route_group__company__is_approved=True,
                )
            )
            .distinct()
            .order_by('route_group', 'go_hour')
        )
