from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from authenticator.models import Company, Driver, Passenger, User
from authenticator.serializers import UserCreateSerializer, UserListAndRetriveSerializer, UserPatchSerializer


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    permission_classes = (IsAuthenticated, IsAdminUser)

    @extend_schema(
        summary='Dados do usuário autenticado',
        description='Retorna ou atualiza os dados do usuário autenticado.',
        responses={200: UserListAndRetriveSerializer, 401: None},
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

        if Driver.objects.filter(user=user).exists():
            user_type = 'driver'
        elif Passenger.objects.filter(user=user).exists():
            user_type = 'passenger'
        elif Company.objects.filter(user=user).exists():
            user_type = 'company'
        else:
            user_type = 'admin'

        data['type'] = user_type

        return Response(data, status=status.HTTP_200_OK)

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
