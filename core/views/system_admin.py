from rest_framework.viewsets import ModelViewSet

from core.models import System_Admin
from core.serializers import System_AdminSerializer


class System_AdminViewSet(ModelViewSet):
    queryset = System_Admin.objects.all()
    serializer_class = System_AdminSerializer
