from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompanyOwner
from core.models.company import Company
from core.serializers.company import CompanyCreateSerializer, CompanyListAndRetrieveSerializer, CompanyPatchSerializer


class CompanyViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        # Permite qualquer um criar uma empresa...
        if self.request.method == 'POST':
            permission_classes = [AllowAny]
        # Permite qualquer um listar empresas...
        elif self.request.method in SAFE_METHODS:
            permission_classes = [AllowAny]
        # Só permite deletar e atualizar se estiver autenticado e for dono da empresa...
        else:
            permission_classes = [IsAuthenticated, IsCompanyOwner]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        # Define serializer de criação para ação de criar (método post)...
        if self.action == 'create':
            return CompanyCreateSerializer
        # Define serializer de criação para ação de atualizar parcialmente (método patch)...
        elif self.action == 'partial_update':
            return CompanyPatchSerializer
        # Define serializer de listagem para ação de listar (método get com ou sem parâmetro de id)...
        else:
            return CompanyListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        # Permite que os administradores do sistema ou super-usuários possam ver todas as empresas...
        if user.is_staff or user.is_superuser:
            return Company.objects.all().order_by('id')

        # Permite que o usuário possa listar a própria empresa usando método retrieve,
        # mesmo que ela não esteja aprovada no sistema...
        if self.action != 'list' and user.is_authenticated:
            return Company.objects.filter(Q(is_approved=True) | Q(user=user)).order_by('id')

        # Não permite que usuários comuns possam ver empresas que não estão aprovadas no sistema...
        return Company.objects.filter(is_approved=True).order_by('id')
