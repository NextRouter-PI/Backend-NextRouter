from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsCompanyOwner
from authenticator.models.company import Company
from authenticator.models.company_route_group import CompanyRouteGroup
from authenticator.serializers.company_route_group import CompanyRouteGroupSerializer


class CompanyGroupRouteViewSet(ModelViewSet):
    serializer_class = CompanyRouteGroupSerializer
    http_method_names = ('get', 'post', 'patch', 'delete')

    def get_permissions(self):
        if self.request.method == 'POST':
            permission_classes = [
                IsAuthenticated,
                IsCompany,
            ]
        elif self.request.method in SAFE_METHODS:
            permission_classes = [AllowAny]
        else:
            permission_classes = [
                IsAuthenticated,
                IsCompanyOwner,
            ]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        company = Company.objects.get(user=self.request.user)
        return serializer.save(company=company)

    def get_queryset(self):
        return CompanyRouteGroup.objects.select_related('company', 'company__user').all()
