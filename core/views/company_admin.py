from rest_framework.viewsets import ModelViewSet

from core.models import Company_Admin
from core.serializers import Company_AdminSerializer


class Company_AdminViewSet(ModelViewSet):
    queryset = Company_Admin.objects.all()
    serializer_class = Company_AdminSerializer
