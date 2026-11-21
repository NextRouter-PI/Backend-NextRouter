from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from modules.accounts.api.serializers import UserCreateSerializer, UserPatchSerializer, UserReadSerializer
from modules.accounts.models import User
from modules.accounts.services import deactivate_account
from shared.exceptions import DomainError
from shared.openapi import RESP_400_VALIDATION, RESP_401_UNAUTHORIZED, document_viewset


def _resolve_user_type(user: User) -> str:
    for profile_attr in ('driver', 'passenger', 'company'):
        if getattr(user, profile_attr, None) is not None:
            return profile_attr
    return 'admin'


@document_viewset(
    'Contas',
    'usuário',
    'usuários',
    read='Apenas administradores da plataforma consultam usuários; GET /users/me/ retorna a própria conta.',
    create='Apenas administradores criam usuários; o cadastro público com código usa /registration/confirm/.',
    change='Apenas administradores editam usuários. E-mail e senha são ignorados; use os fluxos dedicados.',
    delete='Apenas administradores desativam usuários; o último administrador ativo não pode ser desativado.',
    read_response=UserReadSerializer,
    create_response=UserCreateSerializer,
    update_response=UserPatchSerializer,
    delete_status=200,
)
class UserViewSet(ModelViewSet):
    queryset = User.objects.select_related('profile_picture', 'driver', 'passenger', 'company')
    permission_classes = (IsAuthenticated, IsAdminUser)

    @extend_schema(
        methods=['GET'],
        tags=['Contas'],
        summary='Consulte sua conta',
        description='Somente titular autenticado consulta dados pessoais da própria conta.',
        responses={200: UserReadSerializer, 401: RESP_401_UNAUTHORIZED},
    )
    @extend_schema(
        methods=['PATCH'],
        tags=['Contas'],
        summary='Atualize sua conta',
        description='Somente titular autenticado atualiza dados pessoais; e-mail e senha são ignorados.',
        request=UserPatchSerializer,
        responses={200: UserReadSerializer, 400: RESP_400_VALIDATION, 401: RESP_401_UNAUTHORIZED},
    )
    @action(detail=False, methods=['get', 'patch'], permission_classes=[IsAuthenticated])
    def me(self, request):
        user = User.objects.select_related('profile_picture', 'driver', 'passenger', 'company').get(pk=request.user.pk)

        if request.method == 'PATCH':
            serializer = UserPatchSerializer(user, data=request.data, partial=True, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

        data = UserReadSerializer(user, context=self.get_serializer_context()).data
        data['type'] = _resolve_user_type(user)
        return Response(data, status=status.HTTP_200_OK)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        if self.request.method in {'PATCH', 'PUT'}:
            return UserPatchSerializer
        return UserReadSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            deactivate_account(actor_id=request.user.pk, user_id=instance.pk)
        except DomainError as exc:
            raise ValidationError(exc.messages) from exc

        return Response(status=status.HTTP_200_OK)
