from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompanyOwner, IsPassenger, IsPassengerOwner
from core.models.lost_item import LostItem
from core.serializers.lost_item import LostItemCreateSerializer


class LostItemViewSet(ModelViewSet):
    def get_serializer_class(self):
        if self.action == 'create':
            return LostItemCreateSerializer
        return

    def get_permissions(self):
        # Permite que apenas passageiros possam reportar itens perdidos...
        if self.request.method == 'POST':
            permission_classes = [IsAuthenticated, IsPassenger]
        # Permite que apenas o usuário dono ou sua empresa possa listar os items perdidos...
        elif self.request.method in SAFE_METHODS:
            permission_classes = [IsAuthenticated, IsPassengerOwner | IsCompanyOwner]
        # Só permite deletar e atualizar se for o passageiro dono do item perdido..
        else:
            permission_classes = [IsAuthenticated, IsPassengerOwner]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user

        # Permite que os administradores e super-usuários do sistema listem todos os itens perdidos...
        if user.is_staff or user.is_superuser:
            return LostItem.objects.all()

        # Retorna itens perdidos pertencentes ao passageiro logado
        # OU itens pertencentes à empresa logada (se o item estiver numa rota/grupo da empresa)
        return (
            LostItem.objects.filter(Q(passenger__user=user) | Q(route__company__user=user)).distinct().order_by('-id')
        )
