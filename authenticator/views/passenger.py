from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompanyOwner, IsUserOwner
from authenticator.mixins.is_approved import ApproveProfileMixin
from authenticator.models.passenger import Passenger
from authenticator.serializers.passenger import (
    PassengerCreateSerializer,
    PassengerListAndRetrieveSerializer,
    PassengerPatchSerializer,
    PassengerRouteGroupRequestSerializer,
)


class PassengerViewSet(ApproveProfileMixin, ModelViewSet):
    queryset = Passenger.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [AllowAny]
        elif self.action in {'partial_update', 'destroy'}:
            permission_classes = [IsAuthenticated, (IsUserOwner | IsCompanyOwner)]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return PassengerCreateSerializer
        elif self.action == 'partial_update':
            return PassengerPatchSerializer
        else:
            return PassengerListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff or user.is_superuser:
            return Passenger.objects.select_related('user', 'route_group').all().order_by('id')

        return (
            Passenger.objects
            .filter(Q(user=user) | Q(route_group__company__user=user) | Q(route_group__drivers__user=user))
            .distinct()
            .select_related('user', 'route_group')
            .order_by('id')
        )

    @action(
        detail=True,
        methods=['patch'],
        url_path='request-route-group',
        permission_classes=[IsAuthenticated, IsUserOwner],
    )
    def request_route_group(self, request, pk=None):
        """
        Permite que o próprio passageiro peça para entrar num grupo de rota de uma
        empresa (autocadastro). Fica pendente (`is_approved=False`) até a empresa
        aprovar — diferente do PATCH genérico, que só a empresa pode usar para
        definir `route_group` diretamente.
        """
        instance = self.get_object()
        serializer = PassengerRouteGroupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance.route_group = serializer.validated_data['route_group']
        instance.is_approved = False
        instance.save(update_fields=['route_group', 'is_approved'])

        return Response(
            PassengerListAndRetrieveSerializer(instance).data,
            status=status.HTTP_200_OK,
        )
