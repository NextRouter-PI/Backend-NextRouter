from django.db.models import Q
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsUserOwner
from authenticator.models.passenger import Passenger
from authenticator.serializers.passenger import (
    PassengerCreateSerializer,
    PassengerListAndRetrieveSerializer,
    PassengerPatchSerializer,
)


class PassengerViewSet(ModelViewSet):
    queryset = Passenger.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [AllowAny]
        elif self.action in {'partial_update', 'destroy'}:
            permission_classes = [IsAuthenticated, IsUserOwner]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return PassengerCreateSerializer
        elif self.action == 'partial_update':
            return PassengerPatchSerializer
        return PassengerListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff or user.is_superuser:
            return Passenger.objects.select_related('user', 'group_route').all().order_by('id')

        return (
            Passenger.objects
            .filter(Q(user=user) | Q(route_group__company__user=user) | Q(route_group__drivers__user=user))
            .distinct()
            .select_related('user', 'route_group')
            .order_by('id')
        )
