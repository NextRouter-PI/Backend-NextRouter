from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from modules.organizations.api.serializers.passenger import (
    PassengerCreateSerializer,
    PassengerListAndRetrieveSerializer,
    PassengerPatchSerializer,
    PassengerRouteGroupRequestSerializer,
)
from modules.organizations.mixins.is_approved import ApproveProfileMixin, clear_approval_notification_key
from modules.organizations.models.passenger import Passenger
from modules.organizations.permissions import IsCompanyOwner, IsUserOwner
from shared.openapi import (
    RESP_400_VALIDATION,
    RESP_401_UNAUTHORIZED,
    RESP_403_FORBIDDEN,
    RESP_404_NOT_FOUND,
    document_viewset,
)


@document_viewset(
    'Vínculos',
    'passageiro',
    'passageiros',
    read=(
        'Autenticado: o aluno vê seu perfil; empresa aprovada vê seus vinculados (inclusive pendentes); '
        'motorista aprovado vê apenas alunos aprovados do grupo.'
    ),
    create='Cadastro público do próprio aluno exige código de e-mail; o vínculo com a empresa requer aprovação.',
    change='O aluno edita seu perfil; empresa aprovada gerencia vínculos do grupo. E-mail e senha são ignorados.',
    read_response=PassengerListAndRetrieveSerializer,
    create_response=PassengerCreateSerializer,
    update_response=PassengerPatchSerializer,
    public_create=True,
)
class PassengerViewSet(ApproveProfileMixin, ModelViewSet):
    queryset = Passenger.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_fields = ('route_group', 'is_approved')

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [AllowAny]
        elif self.action in {'partial_update', 'destroy'}:
            permission_classes = [IsAuthenticated, (IsUserOwner | IsCompanyOwner)]
        elif self.action in {'approve', 'reject'}:
            permission_classes = [IsAuthenticated, IsCompanyOwner]
        elif self.action == 'request_route_group':
            permission_classes = [IsAuthenticated, IsUserOwner]
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
        base_queryset = Passenger.objects.select_related(
            'user',
            'user__profile_picture',
            'route_group',
            'route_group__company',
        )

        if user.is_staff or user.is_superuser:
            return base_queryset.order_by('id')

        return (
            base_queryset
            .filter(
                Q(user=user)
                | Q(route_group__company__user=user, route_group__company__is_approved=True)
                | Q(
                    route_group__drivers__user=user,
                    route_group__drivers__is_approved=True,
                    route_group__company__is_approved=True,
                    is_approved=True,
                )
            )
            .distinct()
            .order_by('id')
        )

    @extend_schema(
        tags=['Vínculos'],
        summary='Peça entrada no grupo como aluno',
        description=(
            'Somente o próprio aluno autenticado solicita entrada em grupo de empresa aprovada. '
            'Fica pendente até aprovação; repetir pedido pendente retorna o vínculo.'
        ),
        request=PassengerRouteGroupRequestSerializer,
        responses={
            200: PassengerListAndRetrieveSerializer,
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
            404: RESP_404_NOT_FOUND,
        },
        examples=[
            OpenApiExample('Grupo escolhido', value={'route_group': 1}, request_only=True),
            OpenApiExample(
                'Pedido pendente',
                value={
                    'id': 1,
                    'user_data': {'id': '00000000-0000-4000-8000-000000000001', 'name': 'Aluno Fictício'},
                    'route_group': 1,
                    'review_status': 'pending',
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    @action(
        detail=True,
        methods=['patch'],
        url_path='request-route-group',
        permission_classes=[IsAuthenticated, IsUserOwner],
    )
    @transaction.atomic
    def request_route_group(self, request, pk=None):
        """
        Permite que o próprio passageiro peça para entrar num grupo de rota de uma
        empresa (autocadastro). Fica pendente (`is_approved=False`) até a empresa
        aprovar — diferente do PATCH genérico, que só a empresa pode usar para
        definir `route_group` diretamente.
        """
        instance = self.get_object()
        instance = Passenger.objects.select_for_update().get(pk=instance.pk)
        serializer = PassengerRouteGroupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if instance.route_group_id == serializer.validated_data['route_group'].pk and instance.is_approved:
            return Response({'detail': 'Você já participa deste grupo.'}, status=status.HTTP_400_BAD_REQUEST)
        if instance.route_group_id == serializer.validated_data['route_group'].pk and not instance.is_rejected:
            return Response(PassengerListAndRetrieveSerializer(instance, context={'request': request}).data)

        clear_approval_notification_key(instance, instance.route_group_id)
        instance.route_group = serializer.validated_data['route_group']
        instance.is_approved = False
        instance.is_rejected = False
        instance.save(update_fields=['route_group', 'is_approved', 'is_rejected'])

        return Response(
            PassengerListAndRetrieveSerializer(instance, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )
