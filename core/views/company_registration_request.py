from rest_framework.viewsets import ModelViewSet

from core.models import Company_Registration_Request
from core.serializers import Company_Registration_RequestSerializer


class Company_Registration_RequestViewSet(ModelViewSet):
    queryset = Company_Registration_Request.objects.all()
    serializer_class = Company_Registration_RequestSerializer
