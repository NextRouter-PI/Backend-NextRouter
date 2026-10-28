from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from modules.organizations.permissions import IsConfirmationOwner
from modules.transport.api.serializers.confirm_passenger_route import (
    ConfirmPassengerRouteCreateSerializer,
    ConfirmPassengerRouteListAndRetrieveSerializer,
)
from modules.transport.models.confirm_passenger_route import ConfirmPassengerRoute
from modules.transport.models.travel import Travel
from shared.openapi import document_viewset


@document_viewset(
    'Presença',
    'confirmação de presença',
    'confirmações de presença',
    read=(
        'Aluno vê a sua; empresa e motorista aprovados veem as confirmações da própria viagem; administrador vê todas.'
    ),
    create='Aluno aprovado no grupo registra presença apenas em viagem agendada ou em andamento.',
    change='Use a ação /confirm/ para confirmar presença na viagem.',
    read_response=ConfirmPassengerRouteListAndRetrieveSerializer,
    create_response=ConfirmPassengerRouteCreateSerializer,
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
        permission_classes = [IsAuthenticated, IsConfirmationOwner] if self.action == 'confirm' else [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return ConfirmPassengerRouteCreateSerializer
        return ConfirmPassengerRouteListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = ConfirmPassengerRoute.objects.select_related(
            'travel',
            'travel__path',
            'travel__path__route_group',
            'user',
        ).order_by('-created_at')

        if user.is_staff or user.is_superuser:
            return queryset

        return queryset.filter(
            Q(user=user)
            | Q(travel__company__user=user, travel__company__is_approved=True)
            | Q(travel__driver__user=user, travel__driver__is_approved=True)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save()

    @extend_schema(
        tags=['Presença'],
        summary='Confirme presença na viagem',
        description=(
            'Apenas o próprio aluno aprovado no grupo, em viagem agendada ou em andamento. '
            'Marca presença como confirmada; repetir é idempotente.'
        ),
        request=None,
        responses={200: ConfirmPassengerRouteListAndRetrieveSerializer},
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsConfirmationOwner])
    @transaction.atomic
    def confirm(self, request, pk=None):
        confirmation = self.get_object()
        Travel.objects.select_for_update().get(pk=confirmation.travel_id)
        confirmation = (
            ConfirmPassengerRoute.objects
            .select_for_update()
            .select_related('travel__path__route_group', 'user')
            .get(pk=confirmation.pk)
        )
        self.check_object_permissions(request, confirmation)
        if confirmation.travel.status not in {Travel.Status.SCHEDULED, Travel.Status.IN_PROGRESS}:
            return Response(
                {'detail': 'Esta viagem não está aceitando confirmações.'}, status=status.HTTP_400_BAD_REQUEST
            )
        if not confirmation.travel.path.route_group.passengers.filter(user=request.user, is_approved=True).exists():
            return Response({'detail': 'Você não participa deste grupo.'}, status=status.HTTP_403_FORBIDDEN)
        if not confirmation.confirm:
            confirmation.confirm = True
            confirmation.save(update_fields=['confirm'])

        serializer = ConfirmPassengerRouteListAndRetrieveSerializer(confirmation)
        return Response(serializer.data, status=status.HTTP_200_OK)
