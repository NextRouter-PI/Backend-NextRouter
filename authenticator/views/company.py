from django.db.models import Q
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsUserOwner
from authenticator.filters.compay import CompanyFilter
from authenticator.models.company import Company
from authenticator.serializers.company import (
    CompanyCreateSerializer,
    CompanyListAndRetrieveSerializer,
    CompanyPatchSerializer,
)


class CompanyViewSet(ModelViewSet):
    queryset = Company.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_class = CompanyFilter

    def get_permissions(self):
        if self.action == 'create' or self.action in {'list', 'retrieve'}:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated, IsUserOwner]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyCreateSerializer
        elif self.action == 'partial_update':
            return CompanyPatchSerializer
        return CompanyListAndRetrieveSerializer

    def get_queryset(self):
        queryset = Company.objects.select_related('user').order_by('id')

        user = self.request.user

        if user.is_staff or user.is_superuser:
            return queryset

        if self.action != 'list' and user.is_authenticated:
            return queryset.filter(Q(is_approved=True) | Q(user=user))

        return queryset.filter(is_approved=True)
