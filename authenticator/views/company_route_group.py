from django.db.models import Q
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsCompanyOwner
from authenticator.models.company_route_group import CompanyRouteGroup
from authenticator.serializers.company_route_group import (
    CompanyRouteGroupCreateSerializer,
    CompanyRouteGroupListAndRetrieveSerializer,
    CompanyRouteGroupPatchSerializer,
)


class CompanyGroupRouteViewSet(ModelViewSet):
    queryset = CompanyRouteGroup.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [
                IsAuthenticated,
                IsCompany,
            ]
        elif self.action in {'list', 'retrieve'}:
            permission_classes = [AllowAny]
        else:
            permission_classes = [
                IsAuthenticated,
                IsCompanyOwner,
            ]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyRouteGroupCreateSerializer
        elif self.action == 'partial_update':
            return CompanyRouteGroupPatchSerializer
        return CompanyRouteGroupListAndRetrieveSerializer

    def get_queryset(self):
        queryset = CompanyRouteGroup.objects.select_related('company', 'company__user').order_by('id')
        user = self.request.user

        if user.is_staff or user.is_superuser:
            return queryset

        if self.action != 'list' and user.is_authenticated:
            return queryset.filter(Q(company__is_approved=True) | Q(company__user=user))

        return queryset.filter(company__is_approved=True)
