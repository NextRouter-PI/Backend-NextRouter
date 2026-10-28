from django.db import transaction
from django.db.models import Avg, Count, Q
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from modules.organizations.api.serializers.driver import (
    DriverCreateSerializer,
    DriverListAndRetrieveSerializer,
    DriverPatchSerializer,
    DriverRouteGroupRequestSerializer,
)
from modules.organizations.mixins.is_approved import ApproveProfileMixin, clear_approval_notification_key
from modules.organizations.models.driver import Driver
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
    'motorista',
    'motoristas',
    read=(
        'Autenticado: motorista vê seu perfil; empresa aprovada vê seus vinculados (inclusive pendentes); '
        'aluno aprovado vê apenas motoristas aprovados do grupo.'
    ),
    create='Cadastro público do próprio motorista exige código de e-mail; o vínculo com a empresa requer aprovação.',
    change='O motorista edita seu perfil; empresa aprovada gerencia vínculos do grupo. E-mail e senha são ignorados.',
    read_response=DriverListAndRetrieveSerializer,
    create_response=DriverCreateSerializer,
    update_response=DriverPatchSerializer,
    public_create=True,
)
class DriverViewSet(ApproveProfileMixin, ModelViewSet):
    queryset = Driver.objects.all()
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
            return DriverCreateSerializer
        elif self.action == 'partial_update':
            return DriverPatchSerializer
        else:
            return DriverListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user
        base_queryset = Driver.objects.select_related(
            'user',
            'user__profile_picture',
            'route_group',
            'route_group__company',
            'cnh',
        ).annotate(
            _average_rating=Avg('ratings__score'),
            _ratings_count=Count('ratings', distinct=True),
        )

        if user.is_staff or user.is_superuser:
            return base_queryset.order_by('id')

        return (
            base_queryset
            .filter(
                Q(user=user)
                | Q(route_group__company__user=user, route_group__company__is_approved=True)
                | Q(
                    route_group__passengers__user=user,
                    route_group__passengers__is_approved=True,
                    route_group__company__is_approved=True,
                    is_approved=True,
                )
            )
            .distinct()
            .order_by('id')
        )

    @extend_schema(
        tags=['Vínculos'],
        summary='Peça entrada no grupo como motorista',
        description=(
            'Somente o próprio motorista autenticado solicita grupo de empresa aprovada; '
            'troca de grupo remove vínculo anterior com veículo e exige nova aprovação.'
        ),
        request=DriverRouteGroupRequestSerializer,
        responses={
            200: DriverListAndRetrieveSerializer,
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
            404: RESP_404_NOT_FOUND,
        },
        examples=[OpenApiExample('Grupo escolhido', value={'route_group': 1}, request_only=True)],
    )
    @action(
        detail=True,
        methods=['patch'],
        url_path='request-route-group',
        permission_classes=[IsAuthenticated, IsUserOwner],
    )
    @transaction.atomic
    def request_route_group(self, request, pk=None):
        instance = self.get_object()
        instance = Driver.objects.select_for_update().get(pk=instance.pk)
        serializer = DriverRouteGroupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_group = serializer.validated_data['route_group']
        if instance.route_group_id == target_group.pk and instance.is_approved:
            return Response({'detail': 'Você já participa deste grupo.'}, status=status.HTTP_400_BAD_REQUEST)
        if instance.route_group_id == target_group.pk and not instance.is_rejected:
            return Response(DriverListAndRetrieveSerializer(instance, context={'request': request}).data)

        old_group_id = instance.route_group_id
        clear_approval_notification_key(instance, old_group_id)
        instance.route_group = target_group
        instance.is_approved = False
        instance.is_rejected = False
        instance.save(update_fields=['route_group', 'is_approved', 'is_rejected'])
        if old_group_id and old_group_id != target_group.pk:
            from modules.transport.models.vehicle import Vehicle

            Vehicle.objects.filter(driver=instance, route_group_id=old_group_id).update(driver=None)

        return Response(
            DriverListAndRetrieveSerializer(instance, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )
