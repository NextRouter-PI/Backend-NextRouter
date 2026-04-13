from rest_framework.viewsets import ModelViewSet

from core.models import Driver
from core.serializers import DriverSerializer


class DriverViewSet(ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
