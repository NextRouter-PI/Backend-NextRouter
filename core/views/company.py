from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompanyOwnerOrReadOnly
from core.models.company import Company
from core.serializers.company import CompanyRegistrationSerializer, CompanySerializer


class CompanyViewSet(ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    http_method_names = ['get', 'patch', 'delete', 'head', 'options', 'trace']
    permission_classes = [IsCompanyOwnerOrReadOnly]


class CompanyRegistrationViewSet(CreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanyRegistrationSerializer
    permission_classes = [AllowAny]
