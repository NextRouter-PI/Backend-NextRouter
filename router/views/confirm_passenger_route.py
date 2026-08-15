from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from app.permissions import IsConfirmationOwner
from router.models.confirm_passenger_route import ConfirmPassengerRoute
from router.serializers.confirm_passenger_route import (
    ConfirmPassengerRouteListAndRetrieveSerializer,
)


class ConfirmPassengerRouteViewSet(ReadOnlyModelViewSet):
    queryset = ConfirmPassengerRoute.objects.all()

    def get_permissions(self):
        permission_classes = [IsAuthenticated, IsConfirmationOwner] if self.action == 'confirm' else [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        return ConfirmPassengerRouteListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = ConfirmPassengerRoute.objects.select_related(
            'travel',
            'user',
        ).order_by('-created_at')

        if user.is_staff or user.is_superuser:
            return queryset

        return queryset.filter(Q(user=user) | Q(travel__company__user=user) | Q(travel__driver__user=user)).distinct()

    @extend_schema(
        summary='Confirmar presença na rota.',
        request=None,
        responses={200: ConfirmPassengerRouteListAndRetrieveSerializer},
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsConfirmationOwner])
    def confirm(self, request, pk=None):
        confirmation = self.get_object()
        confirmation.confirm = True
        # confirmation.confirm = not confirmation.confirm
        confirmation.save(update_fields=['confirm'])

        serializer = self.get_serializer(confirmation)
        return Response(serializer.data, status=status.HTTP_200_OK)
