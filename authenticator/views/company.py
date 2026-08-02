from django.db.models import Q
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompanyOwner
from authenticator.models.company import Company
from authenticator.serializers.company import (
    CompanyCreateSerializer,
    CompanyListAndRetrieveSerializer,
    CompanyPatchSerializer,
)


class CompanyViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']

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
        elif self.action == 'partial_update':
            return CompanyPatchSerializer
        elif self.action in {'list', 'retrieve'}:
            return CompanyListAndRetrieveSerializer
        return CompanyListAndRetrieveSerializer

    def get_queryset(self):
        queryset = Company.objects.select_related('user').order_by('id')

        user = self.request.user

        if user.is_staff or user.is_superuser:
            return queryset

        if self.action != 'list' and user.is_authenticated:
            return queryset.filter(Q(is_approved=True) | Q(user=user))

        return queryset.filter(is_approved=True)
