from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsVehicleOwner
from router.models.vehicle import Vehicle
from router.serializers.vehicle import VehicleCreateSerializer, VehicleListAndRetrieveSerializer, VehiclePatchSerializer


class VehicleViewSet(ModelViewSet):
    queryset = Vehicle.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')

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
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
            Q(route_group__company__user=user)
            | Q(route_group__drivers__user=user)
            | Q(route_group__passengers__user=user),
        ).distinct()
