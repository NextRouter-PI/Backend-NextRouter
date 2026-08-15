from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsPathOwner
from router.models.path import Path
from router.serializers.path import PathSerializer


class PathViewSet(ModelViewSet):
    queryset = Path.objects.all()
    serializer_class = PathSerializer
    http_method_names = (
        'get',
        'post',
        'patch',
        'delete',
    )

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsCompany]
        elif self.action in {'partial_update', 'update', 'destroy'}:
            permission_classes = [IsAuthenticated, IsCompany, IsPathOwner]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user

        queryset = Path.objects.select_related(
            'group',
            'group__company',
            'group__company__user',
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return Path.objects.filter(
            Q(route_group__company__user=user)
            | Q(route_group__drivers__user=user)
            | Q(route_group__passengers__user=user),
        ).distinct()
