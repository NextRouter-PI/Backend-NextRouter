from rest_framework.viewsets import ModelViewSet

from core.models import Contract_Request
from core.serializers import Contract_RequestSerializer


class Contract_RequestViewSet(ModelViewSet):
    queryset = Contract_Request.objects.all()
    serializer_class = Contract_RequestSerializer
