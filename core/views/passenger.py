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
    http_method_names = ['get', 'post', 'patch', 'options', 'delete']

    def get_permissions(self):
        # Permite criação pública (cadastro), mas exige autenticação para o resto
        if self.action == 'create':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return PassengerCreateSerializer
        elif self.action == 'partial_update':  # Correção: No DRF o método PATCH aciona a action 'partial_update'
            return PassengerPatchSerializer
        elif self.action == 'list':
            return PassengerListAndRetrieveSerializer
        return PassengerListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        # Se o usuário não estiver autenticado (durante um POST de criação, por exemplo)
        if not user or user.is_anonymous:
            return Passenger.objects.none()

        # 1. Admin/Staff visualiza todos os passageiros do sistema
        if user.is_staff or user.is_superuser:
            return Passenger.objects.all().order_by('id')

        # 2. Filtro dinâmico com OR (Q):
        # - Traz o próprio passageiro (se auto-listar)
        # - Traz passageiros cujas rotas pertencem à empresa onde o usuário logado é o dono
        return Passenger.objects.filter(Q(user=user) | Q(group_route__company__user=user)).distinct().order_by('id')
