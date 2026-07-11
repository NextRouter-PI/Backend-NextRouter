from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsPassengerOwnerOrRouteCompanyOrDriver
from core.models.confirm_passenger_route import ConfirmPassengerRoute
from core.serializers.confirm_passenger_route import (
    ConfirmPassengerRouteCreateSerializer,
    ConfirmPassengerRouteListAndRetrieveSerializer,
)


class ConfirmPassengerRouteViewSet(ModelViewSet):
    http_method_names = ['get', 'patch', 'options']
    permission_classes = [IsAuthenticated, IsPassengerOwnerOrRouteCompanyOrDriver]

    def get_queryset(self):
        user = self.request.user
        return ConfirmPassengerRoute.objects.filter(
            Q(user=user) | Q(route__driver__user=user) | Q(route__company__user=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action in set(['partial_update', 'update']):
            return ConfirmPassengerRouteCreateSerializer
        return ConfirmPassengerRouteListAndRetrieveSerializer
