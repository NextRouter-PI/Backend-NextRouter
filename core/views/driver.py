from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.models.driver import Driver
from core.serializers.driver import DriverSerializer


class DriverViewSet(ModelViewSet):
    queryset = Driver.objects.all()
    serializer_class = DriverSerializer
    permission_classes = [IsAuthenticated]
