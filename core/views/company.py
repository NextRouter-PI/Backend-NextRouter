from rest_framework.viewsets import ModelViewSet

from core.models import Company
from core.serializers import CompanySerializer


class CompanyViewSet(ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
