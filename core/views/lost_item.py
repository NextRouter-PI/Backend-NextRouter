from rest_framework.viewsets import ModelViewSet

from core.models.lost_item import LostItem
from core.serializers.lost_item import LostItemSerializer


class LostItemViewSet(ModelViewSet):
    serializer_class = LostItemSerializer
    queryset = LostItem.objects.all()
