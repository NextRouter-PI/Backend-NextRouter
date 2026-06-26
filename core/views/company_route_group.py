from rest_framework.permissions import SAFE_METHODS, IsAdminUser, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsCompanyOwner
from core.models.company import Company
from core.models.company_route_group import CompanyRouteGroup
from core.serializers.company_route_group import CompanyRouteGroupSerializer


class CompanyGroupRouteViewSet(ModelViewSet):
    queryset = CompanyRouteGroup.objects.all()
    serializer_class = CompanyRouteGroupSerializer
    http_method_names = ['get', 'post', 'patch', 'options', 'delete']

    def get_permissions(self):
        if self.request.method == 'POST':
            permission_classes = [
                IsAuthenticated,
                IsAdminUser,
                IsCompany,
            ]
        else:
            permission_classes = [
                IsAuthenticated,
                IsCompanyOwner,
            ]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        company = Company.objects.get(user=self.request.user)
        serializer.save(company=company)
