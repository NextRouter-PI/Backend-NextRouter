from rest_framework.viewsets import ModelViewSet

from core.models import Route_Group
from core.serializers import Route_GroupSerializer


class Route_GroupViewSet(ModelViewSet):
    queryset = Route_Group.objects.all()
    serializer_class = Route_GroupSerializer
