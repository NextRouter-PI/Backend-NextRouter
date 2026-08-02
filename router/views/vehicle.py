from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsVehicleOwner
from router.models.vehicle import Vehicle
from router.serializers.vehicle import VehicleSerializer


class VehicleViewSet(ModelViewSet):
    serializer_class = VehicleSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsCompany]

        elif self.action in {'partial_update', 'update', 'destroy'}:
            permission_classes = [IsAuthenticated, IsCompany, IsVehicleOwner]

        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user

        queryset = Vehicle.objects.select_related('group', 'group__company', 'group__company__user')

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
            Q(group__company__user=user) | Q(group__drivers__user=user) | Q(group__passengers__user=user)
        ).distinct()
