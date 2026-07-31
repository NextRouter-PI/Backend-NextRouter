from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsPassengerOwnerForUpdateOrRouteStaffForRead
from core.models.confirm_passenger_route import ConfirmPassengerRoute
from core.serializers.confirm_passenger_route import (
    ConfirmPassengerRouteCreateSerializer,
    ConfirmPassengerRouteListAndRetrieveSerializer,
)


class ConfirmPassengerRouteViewSet(ModelViewSet):
    http_method_names = ['get', 'patch']
    permission_classes = [IsAuthenticated, IsPassengerOwnerForUpdateOrRouteStaffForRead]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff or user.is_superuser:
            return ConfirmPassengerRoute.objects.all()

        return ConfirmPassengerRoute.objects.filter(
            # 1. Registros de rotas onde o usuário é a EMPRESA dona
            Q(route__company__user=user)
            |
            # 2. Registros de rotas onde o usuário é o MOTORISTA
            Q(route__driver__user=user)
            |
            # 3. Registros de rotas nas quais o PASSAGEIRO também está confirmado/inscrito
            # (permite que ele veja os outros passageiros da mesma viagem)
            Q(route__confirmations__user=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action in {'partial_update', 'update'}:
            return ConfirmPassengerRouteCreateSerializer
        return ConfirmPassengerRouteListAndRetrieveSerializer
