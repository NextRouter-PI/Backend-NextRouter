from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from modules.organizations.api.filters.route_group import CompanyRouteGroupFilter
from modules.organizations.api.serializers.company_route_group import (
    CompanyRouteGroupCreateSerializer,
    CompanyRouteGroupListAndRetrieveSerializer,
    CompanyRouteGroupPatchSerializer,
)
from modules.organizations.models.company import Company
from modules.organizations.models.company_route_group import CompanyRouteGroup
from modules.organizations.permissions import IsCompany, IsCompanyOwner
from shared.openapi import document_viewset


@document_viewset(
    'Grupos de rota',
    'grupo de rota',
    'grupos de rota',
    read='Consulta pública de grupos de empresas aprovadas; titular também vê seus grupos.',
    create='Apenas empresa aprovada cria grupo de rota e define o CEP comum.',
    change='Apenas empresa aprovada dona do grupo altera ou exclui; vínculos existentes podem impedir exclusão.',
    read_response=CompanyRouteGroupListAndRetrieveSerializer,
    create_response=CompanyRouteGroupCreateSerializer,
    update_response=CompanyRouteGroupPatchSerializer,
    public_read=True,
)
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
        queryset = (
            CompanyRouteGroup.objects
            .select_related('company', 'company__user')
            .annotate(_passengers_count=Count('passengers', distinct=True))
            .order_by('id')
        )
        user = self.request.user

        if user.is_staff or user.is_superuser:
            return queryset

        if user.is_authenticated:
            return queryset.filter(Q(company__is_approved=True) | Q(company__user=user))

        return queryset.filter(company__is_approved=True)
