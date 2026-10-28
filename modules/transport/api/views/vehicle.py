from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from modules.organizations.permissions import IsCompany, IsVehicleOwner
from modules.transport.api.serializers.vehicle import (
    VehicleCreateSerializer,
    VehicleListAndRetrieveSerializer,
    VehiclePatchSerializer,
)
from modules.transport.models.vehicle import Vehicle
from shared.openapi import document_viewset


@document_viewset(
    'Veículos',
    'veículo',
    'veículos',
    read='Empresa, motorista e aluno aprovados veem veículos do próprio grupo; administrador vê todos.',
    create='Empresa aprovada cria veículo ativo ou em manutenção no próprio grupo.',
    change='Apenas empresa aprovada dona do grupo altera/exclui; capacidade e motorista são validados.',
    read_response=VehicleListAndRetrieveSerializer,
    create_response=VehicleCreateSerializer,
    update_response=VehiclePatchSerializer,
)
class VehicleViewSet(ModelViewSet):
    queryset = Vehicle.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_fields = ('route_group', 'driver', 'status')

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsCompany]
        elif self.action in {'destroy', 'partial_update'}:
            permission_classes = [IsAuthenticated, IsCompany, IsVehicleOwner]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return VehicleCreateSerializer
        elif self.action == 'partial_update':
            return VehiclePatchSerializer
        return VehicleListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = Vehicle.objects.select_related(
            'route_group',
            'route_group__company',
            'driver',
            'driver__user',
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
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
            ),
        ).distinct()
