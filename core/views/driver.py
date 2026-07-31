from django.db.models import Q
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.models.driver import Driver
from core.serializers.driver import (
    DriverCreateSerializer,
    DriverListAndRetrieveSerializer,
    DriverPatchSerializer,
)


class DriverViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        # Permite qualquer usuário criar um motorista...
        if self.action == 'create':
            permission_classes = [AllowAny]
        # Não o permite demais ações se o usuário não estiver autenticado...
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        # Define serializador de criação (método post)...
        if self.action == 'create':
            return DriverCreateSerializer
        elif self.action == 'partial_update':
            return DriverPatchSerializer
        return DriverListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        # Permite que os administradores do sistema ou super-usuários possam ver todas os motoristas...
        if user.is_staff or user.is_superuser:
            return Driver.objects.all().order_by('id')
        # Não permite que o usuário veja motoristas que não sejam ele, ou motoristas afiliados a sua empresa...
        else:
            return Driver.objects.filter(Q(user=user) | Q(group_route__company__user=user)).distinct().order_by('id')
