from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsGroupOwner
from core.models.path import Path
from core.serializers.path import PathSerializer


class PathViewSet(ModelViewSet):
    queryset = Path.objects.all()
    serializer_class = PathSerializer

    def get_permissions(self):
        return [IsAuthenticated(), IsGroupOwner()]

    