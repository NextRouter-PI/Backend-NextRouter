from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from app.permissions import IsConfirmationOwner
from router.models.confirm_passenger_route import ConfirmPassengerRoute
from router.serializers.confirm_passenger_route import (
    ConfirmPassengerRouteCreateSerializer,
    ConfirmPassengerRouteListAndRetrieveSerializer,
)


class ConfirmPassengerRouteViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    queryset = ConfirmPassengerRoute.objects.all()
    filterset_fields = ('travel', 'user', 'confirm')

    def get_permissions(self):
        if self.action == 'confirm':
            permission_classes = [IsAuthenticated, IsConfirmationOwner]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return ConfirmPassengerRouteCreateSerializer
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

    def perform_create(self, serializer):
        serializer.save()

    @extend_schema(
        summary='Confirmar presença na rota.',
        request=None,
        responses={200: ConfirmPassengerRouteListAndRetrieveSerializer},
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsConfirmationOwner])
    def confirm(self, request, pk=None):
        confirmation = self.get_object()
        confirmation.confirm = True
        confirmation.save(update_fields=['confirm'])

        serializer = ConfirmPassengerRouteListAndRetrieveSerializer(confirmation)
        return Response(serializer.data, status=status.HTTP_200_OK)
