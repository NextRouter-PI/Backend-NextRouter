from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsCompanyOwner
from core.models.company import Company
from core.models.company_route_group import CompanyRouteGroup
from core.serializers.company_route_group import CompanyRouteGroupSerializer


class CompanyGroupRouteViewSet(ModelViewSet):
    queryset = CompanyRouteGroup.objects.all()
    serializer_class = CompanyRouteGroupSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        # Permite com que apenas empresas possam criar grupos de rotas...
        if self.request.method == 'POST':
            permission_classes = [
                IsAuthenticated,
                IsCompany,
            ]
        # Permite que qualquer um possa listar grupos de rotas...
        elif self.request.method in SAFE_METHODS:
            permission_classes = [AllowAny]
        # Permite que, apenas se o usuário for a empresa dona, possa deletar ou atualizar o grupo...
        else:
            permission_classes = [
                IsAuthenticated,
                IsCompanyOwner,
            ]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        # O grupo de rotas fica associada à empresa que criou...
        company = Company.objects.get(user=self.request.user)
        serializer.save(company=company)
