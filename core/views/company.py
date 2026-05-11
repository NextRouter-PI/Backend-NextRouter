from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompanyOwner
from core.models.company import Company
from core.serializers.company import CompanyCreateSerializer, CompanyListAndRetrieveSerializer, CompanyPatchSerializer


class CompanyViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'options', 'delete']

    def get_permissions(self):
        if self.request.method == 'POST':
            permission_classes = [AllowAny]
        elif self.request.method in SAFE_METHODS:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsCompanyOwner]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyCreateSerializer
        elif self.action == 'patch':
            return CompanyPatchSerializer
        return CompanyListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Company.objects.all()
        if self.action == 'list':
            return Company.objects.filter(is_approved=True)
        if user.is_authenticated:
            return Company.objects.filter(Q(is_approved=True) | Q(user=user))
        return Company.objects.filter(is_approved=True)
