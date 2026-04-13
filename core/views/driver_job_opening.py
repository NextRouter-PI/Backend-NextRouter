from rest_framework.viewsets import ModelViewSet

from core.models import Driver_Job_Opening
from core.serializers import Driver_Job_OpeningSerializer


class Driver_Job_OpeningViewSet(ModelViewSet):
    queryset = Driver_Job_Opening.objects.all()
    serializer_class = Driver_Job_OpeningSerializer
