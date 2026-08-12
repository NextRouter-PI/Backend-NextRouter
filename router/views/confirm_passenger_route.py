from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsConfirmationOwner
from router.models.confirm_passenger_route import ConfirmPassengerRoute
from router.serializers.confirm_passenger_route import (
    ConfirmPassengerRouteListAndRetrieveSerializer,
    ConfirmPassengerRoutePatchSerializer,
)


class ConfirmPassengerRouteViewSet(ModelViewSet):
    http_method_names = (
        'get',
        'patch',
    )

    def get_permissions(self):
        if self.action in {'list', 'retrieve'}:
            permission_classes = [IsAuthenticated]
        elif self.action in {'partial_update', 'update'}:
            permission_classes = [IsAuthenticated, IsConfirmationOwner]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user

        queryset = ConfirmPassengerRoute.objects.select_related(
            'travel',
            'user',
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
            Q(user=user) | Q(travel__company__user=user) | Q(travel__driver__user=user),
        ).distinct()

    def get_serializer_class(self):
        if self.action in {'partial_update', 'update'}:
            return ConfirmPassengerRoutePatchSerializer
        return ConfirmPassengerRouteListAndRetrieveSerializer
