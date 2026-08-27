from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsCompanyOwner
from authenticator.models.company import Company
from authenticator.models.company_route_group import CompanyRouteGroup
from authenticator.serializers.company_route_group import (
    CompanyRouteGroupCreateSerializer,
    CompanyRouteGroupListAndRetrieveSerializer,
    CompanyRouteGroupPatchSerializer,
)
from authenticator.filters.route_group import CompanyRouteGroupFilter


class CompanyGroupRouteViewSet(ModelViewSet):
    queryset = CompanyRouteGroup.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_class = CompanyRouteGroupFilter

    def perform_create(self, serializer):
        company = Company.objects.get(user=self.request.user)
        serializer.save(company=company)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'Não é possível excluir esta rota pois ainda há veículos, motoristas ou '
                        'passageiros vinculados a ela. Desvincule-os da rota antes de excluí-la.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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

        if user.is_authenticated:
            return queryset.filter(Q(company__is_approved=True) | Q(company__user=user))

        return queryset.filter(company__is_approved=True)
