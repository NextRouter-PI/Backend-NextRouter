# from drf_spectacular.utils import extend_schema
# from rest_framework.decorators import action
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import User
from core.serializers import UserCreateSerializer, UserListAndRetriveSerializer, UserPatchSerializer


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_serializer_class(self):
        if self.request.method in {'POST', 'PUT'}:
            return UserCreateSerializer
        if self.request.method == 'PATCH':
            return UserPatchSerializer
        return UserListAndRetriveSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_staff and User.objects.filter(is_staff=True, is_active=True).count() <= 1:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.is_active = False
        instance.save(update_fields=['is_active'])

        return Response(status=status.HTTP_200_OK)


"""
    @extend_schema(
        summary='Dados do usuário autenticado',
        description='Retorna os dados do usuário autenticado.',
        responses={200: UserSerializer, 401: None},
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsSelf])
    def me(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)
"""
