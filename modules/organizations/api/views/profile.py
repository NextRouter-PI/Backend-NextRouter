from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from modules.organizations.api.serializers.driver import (
    DriverCreateSerializer,
    DriverListAndRetrieveSerializer,
    DriverPatchSerializer,
)
from modules.organizations.api.serializers.passenger import (
    PassengerCreateSerializer,
    PassengerListAndRetrieveSerializer,
    PassengerPatchSerializer,
)
from modules.organizations.models import CompanyMembership, Driver, Passenger
from modules.transport.access import companies_for
from shared.openapi import document_viewset


class ProfileViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, GenericViewSet
):
    http_method_names = ('get', 'post', 'patch', 'put', 'head', 'options')
    profile_field = None
    filterset_fields = ('id',)

    def get_permissions(self):
        return [AllowAny()] if self.action == 'create' else [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return self.create_serializer_class
        if self.action in ('partial_update', 'update'):
            return self.patch_serializer_class
        return self.serializer_class

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset
        user = self.request.user
        if not user.is_authenticated:
            return self.queryset
        queryset = self.queryset.model.objects.select_related('user')
        if self.action in ('partial_update', 'update'):
            return queryset.filter(user=user)
        linked = CompanyMembership.objects.filter(
            company__in=companies_for(user), status='active', **{f'{self.profile_field}__isnull': False}
        ).values(f'{self.profile_field}_id')
        return queryset.filter(Q(user=user) | Q(pk__in=linked)).distinct().order_by('pk')

    @extend_schema(
        summary='Consulte seu perfil',
        description='Somente o titular. Identidade é separada do vínculo.',
        methods=['GET'],
    )
    @extend_schema(
        summary='Atualize seu perfil',
        description='Somente o titular. Não altera vínculo, grupo ou aprovação.',
        methods=['PATCH'],
    )
    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        instance = get_object_or_404(self.queryset.model, user=request.user)
        if request.method == 'PATCH':
            serializer = self.patch_serializer_class(
                instance, data=request.data, partial=True, context=self.get_serializer_context()
            )
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
        return Response(self.serializer_class(instance, context=self.get_serializer_context()).data)


@document_viewset(
    'Passageiros',
    'passageiro',
    'passageiros',
    read='Titular ou empresa com vínculo ativo; dados mínimos para terceiros.',
    create='Cadastro com código de e-mail, sem grupo ou aprovação empresarial.',
    change='Somente titular altera identidade; não há exclusão empresarial do perfil.',
    read_response=PassengerListAndRetrieveSerializer,
    create_response=PassengerCreateSerializer,
    update_response=PassengerPatchSerializer,
    public_create=True,
)
class PassengerViewSet(ProfileViewSet):
    queryset = Passenger.objects.none()
    serializer_class = PassengerListAndRetrieveSerializer
    create_serializer_class = PassengerCreateSerializer
    patch_serializer_class = PassengerPatchSerializer
    profile_field = 'passenger'


@document_viewset(
    'Motoristas',
    'motorista',
    'motoristas',
    read='Titular ou empresa com vínculo ativo; dados mínimos para terceiros, sem CNH.',
    create='Cadastro com código de e-mail, sem grupo ou aprovação empresarial.',
    change='Somente titular altera identidade; vínculo empresarial usa ações próprias.',
    read_response=DriverListAndRetrieveSerializer,
    create_response=DriverCreateSerializer,
    update_response=DriverPatchSerializer,
    public_create=True,
)
class DriverViewSet(ProfileViewSet):
    queryset = Driver.objects.none()
    serializer_class = DriverListAndRetrieveSerializer
    create_serializer_class = DriverCreateSerializer
    patch_serializer_class = DriverPatchSerializer
    profile_field = 'driver'
