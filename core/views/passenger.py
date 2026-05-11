from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.models.company_route_group import CompanyRouteGroup
from core.models.passenger import Passenger
from core.serializers.passenger import (
    PassengerCreateSerializer,
    PassengerListAndRetrieveSerializer,
    PassengerPatchSerializer,
)


class PassengerViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'options', 'delete']

    def get_permissions(self):
        permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return PassengerCreateSerializer
        elif self.action == 'list':
            return PassengerCreateSerializer
        elif self.action == 'patch':
            return PassengerPatchSerializer
        else:
            return PassengerListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user
        passenger = Passenger.objects.filter(user=user).first()
        group_route = Passenger.objects.filter(group_route=passenger.group_route)
        return group_route
