from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsGroupOwner
from core.models.vehicle import Vehicle
from core.models.company_route_group import CompanyRouteGroup
from core.serializers.path import PathSerializer


class VehicleViewSet(ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = PathSerializer

    def get_permissions(self):
        return [IsAuthenticated(), IsGroupOwner()]

    def perform_create(self, serializer):
        # O grupo de rotas fica associada à empresa que criou...
        company = CompanyRouteGroup.objects.get(user=self.request.user)
        serializer.save(company=company)
