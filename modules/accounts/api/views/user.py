from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from modules.accounts.api.serializers import UserCreateSerializer, UserListAndRetriveSerializer, UserPatchSerializer
from modules.accounts.models import User
from modules.transport.services.common import DomainError
from modules.transport.services.governance import deactivate_account
from shared.openapi import RESP_400_VALIDATION, RESP_401_UNAUTHORIZED, document_viewset


@document_viewset(
    'Contas',
    'usuário',
    'usuários',
    read='Apenas administradores da plataforma consultam usuários; GET /users/me/ retorna a própria conta.',
    create='Apenas administradores criam usuários; o cadastro público com código usa /registration/confirm/.',
    change='Apenas administradores editam usuários. E-mail e senha são ignorados; use os fluxos dedicados.',
    delete='Apenas administradores desativam usuários; o último administrador ativo não pode ser desativado.',
    read_response=UserListAndRetriveSerializer,
    create_response=UserCreateSerializer,
    update_response=UserPatchSerializer,
    delete_status=200,
)
class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    permission_classes = (IsAuthenticated, IsAdminUser)

    @extend_schema(
        methods=['GET'],
        tags=['Contas'],
        summary='Consulte sua conta',
        description='Somente titular autenticado consulta dados pessoais da própria conta.',
        responses={200: UserListAndRetriveSerializer, 401: RESP_401_UNAUTHORIZED},
    )
    @extend_schema(
        methods=['PATCH'],
        tags=['Contas'],
        summary='Atualize sua conta',
        description='Somente titular autenticado atualiza dados pessoais; e-mail e senha são ignorados.',
        request=UserPatchSerializer,
        responses={200: UserListAndRetriveSerializer, 400: RESP_400_VALIDATION, 401: RESP_401_UNAUTHORIZED},
    )
    @action(detail=False, methods=['get', 'patch'], permission_classes=[IsAuthenticated])
    def me(self, request):
        user = request.user

        if request.method == 'PATCH':
            serializer = UserPatchSerializer(user, data=request.data, partial=True, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

        serializer = UserListAndRetriveSerializer(user)
        data = serializer.data

        if hasattr(user, 'driver'):
            user_type = 'driver'
        elif hasattr(user, 'passenger'):
            user_type = 'passenger'
        elif hasattr(user, 'company'):
            user_type = 'company'
        else:
            user_type = 'admin'

        data['type'] = user_type

        return Response(data, status=status.HTTP_200_OK)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        if self.request.method in {'PATCH', 'PUT'}:
            return UserPatchSerializer
        return UserListAndRetriveSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_staff and User.objects.filter(is_staff=True, is_active=True).count() <= 1:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            deactivate_account(actor_id=request.user.pk, user_id=instance.pk)
        except DomainError as exc:
            from rest_framework.exceptions import ValidationError

            raise ValidationError(exc.messages) from exc

        return Response(status=status.HTTP_200_OK)
