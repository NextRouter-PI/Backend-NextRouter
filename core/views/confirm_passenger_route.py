from rest_framework.permissions import SAFE_METHODS, IsAdminUser, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsCompanyOwner
from core.models.company import Company
from core.models.confirm_passenger_route import ConfirmPassengerRoute
from core.serializers.confirm_passenger_route import (
    ConfirmPassengerRouteListAndRetrieveSerializer,
)


class ConfirmPassengerRouteViewSet(ModelViewSet):
    queryset = ConfirmPassengerRoute.objects.all()
    serializer_class = ConfirmPassengerRouteListAndRetrieveSerializer
    http_method_names = ["get","options"]
    permission_classes = [IsAuthenticated]


"""
    def perform_create(self, serializer):
        company = Company.objects.get(user=self.request.user)
        serializer.save(company=company)
"""
