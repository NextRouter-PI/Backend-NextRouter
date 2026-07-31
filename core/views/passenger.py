from django.db.models import Q
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.models.passenger import Passenger
from core.serializers.passenger import (
    PassengerCreateSerializer,
    PassengerListAndRetrieveSerializer,
    PassengerPatchSerializer,
)


class PassengerViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return PassengerCreateSerializer
        elif self.action == 'partial_update':
            return PassengerPatchSerializer
        elif self.action == 'list':
            return PassengerListAndRetrieveSerializer
        else:
            return PassengerListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        # Permite que administradores do sistema e super-usuários possam listar todos os passageiros...
        if user.is_staff or user.is_superuser:
            return Passenger.objects.all().order_by('id')
        # Não permite que o usuário veja passageiros que não sejam ele, ou passageiros afiliados a sua empresa...
        else:
            return Passenger.objects.filter(Q(user=user) | Q(group_route__company__user=user)).distinct().order_by('id')
