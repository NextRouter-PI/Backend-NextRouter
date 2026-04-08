from rest_framework.viewsets import ModelViewSet

from core.models import Company_Profile
from core.serializers import Company_ProfileSerializer


class Company_ProfileViewSet(ModelViewSet):
    queryset = Company_Profile.objects.all()
    serializer_class = Company_ProfileSerializer
