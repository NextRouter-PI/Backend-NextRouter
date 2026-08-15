from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsItemOwner, IsUserOwner
from router.models.lost_item import LostItem
from router.serializers.lost_item import LostItemCreateSerializer, LostItemListAndRetrieveSerializer


class LostItemViewSet(ModelViewSet):
    queryset = LostItem.objects.all()
    http_method_names = (
        'get',
        'post',
        'patch',
        'delete',
    )

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsUserOwner]
        elif self.action in {'partial_update', 'update', 'destroy'}:
            permission_classes = [IsAuthenticated, IsItemOwner]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in {'create', 'partial_update', 'update'}:
            return LostItemCreateSerializer
        return LostItemListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = LostItem.objects.select_related(
            'travel',
            'user',
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
            Q(user=user) | Q(travel__company__user=user),
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
