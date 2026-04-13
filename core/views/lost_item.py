from rest_framework.viewsets import ModelViewSet

from core.models import Lost_Item
from core.serializers import Lost_ItemSerializer


class Lost_ItemViewSet(ModelViewSet):
    queryset = Lost_Item.objects.all()
    serializer_class = Lost_ItemSerializer
