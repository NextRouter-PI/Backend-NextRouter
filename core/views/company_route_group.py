from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompanyOwnerOrReadOnly
from core.models.company import Company
from core.models.company_route_group import CompanyRouteGroup
from core.serializers.company_route_group import CompanyRouteGroupSerializer


class CompanyGroupRouteViewSet(ModelViewSet):
    queryset = CompanyRouteGroup.objects.all()
    serializer_class = CompanyRouteGroupSerializer
    permission_classes = [IsCompanyOwnerOrReadOnly]

    def perform_create(self, serializer):
        company = Company.objects.get(user=self.request.user)
        serializer.save(company=company)
