from django.db.models import Q
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompanyOwner, IsUserOwner
from authenticator.mixins.is_approved import ApproveProfileMixin
from authenticator.models.driver import Driver
from authenticator.serializers.driver import (
    DriverCreateSerializer,
    DriverListAndRetrieveSerializer,
    DriverPatchSerializer,
)


class DriverViewSet(ApproveProfileMixin, ModelViewSet):
    queryset = Driver.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [AllowAny]
        elif self.action in {'partial_update', 'destroy'}:
            permission_classes = [IsAuthenticated, (IsUserOwner | IsCompanyOwner)]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return DriverCreateSerializer
        elif self.action == 'partial_update':
            return DriverPatchSerializer
        else:
            return DriverListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff or user.is_superuser:
            return Driver.objects.select_related('user', 'route_group').all().order_by('id')

        return (
            Driver.objects
            .filter(Q(user=user) | Q(route_group__company__user=user) | Q(route_group__passengers__user=user))
            .distinct()
            .select_related('user', 'route_group')
            .order_by('id')
        )
