from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from modules.organizations.access import companies_for
from modules.organizations.api.filters.company import CompanyFilter, build_route_group_match_q
from modules.organizations.api.serializers.company import (
    CompanyCreateSerializer,
    CompanyListAndRetrieveSerializer,
    CompanyPatchSerializer,
)
from modules.organizations.models.company import Company
from modules.organizations.models.company_route_group import CompanyRouteGroup
from modules.organizations.permissions import IsCompany, IsUserOwner
from modules.transport.models.travel import Travel
from shared.openapi import document_viewset


@document_viewset(
    'Empresas',
    'empresa',
    'empresas',
    read='Listagem pública somente de empresas aprovadas; o titular pode consultar seu próprio cadastro.',
    create='Cadastro público exige código de e-mail; a empresa fica pendente de aprovação pelo administrador.',
    change='Apenas o titular edita ou remove o próprio cadastro; aprovação é feita no Django Admin.',
    read_response=CompanyListAndRetrieveSerializer,
    create_response=CompanyCreateSerializer,
    update_response=CompanyPatchSerializer,
    public_read=True,
    public_create=True,
)
class CompanyViewSet(ModelViewSet):
    queryset = Company.objects.all()
    http_method_names = ('get', 'post', 'patch', 'head', 'options')
    filterset_class = CompanyFilter

    def get_permissions(self):
        if self.action == 'create' or self.action in {'list', 'retrieve', 'served_cities'}:
            permission_classes = [AllowAny]
        elif self.action == 'me':
            permission_classes = [IsAuthenticated]
        elif self.action == 'stats':
            permission_classes = [IsAuthenticated, IsCompany]
        else:
            permission_classes = [IsAuthenticated, IsUserOwner]
        return [permission() for permission in permission_classes]

    @extend_schema(
        tags=['Empresas'],
        summary='Consulte cidades atendidas por grupos de rota',
        description=(
            'Retorna pares distintos de cidade e UF atendidos por grupos de rota de empresas aprovadas e ativas, '
            'sem expor endereços ou coordenadas operacionais.'
        ),
        parameters=[
            OpenApiParameter(
                name='state',
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description='UF (2 letras) para filtrar cidades atendidas.',
            ),
        ],
        responses={
            200: inline_serializer(
                'ServedCitiesResponse',
                fields={
                    'cities': serializers.ListField(
                        child=inline_serializer(
                            'ServedCityItem',
                            fields={
                                'city': serializers.CharField(),
                                'state': serializers.CharField(),
                            },
                        )
                    )
                },
            )
        },
    )
    @action(detail=False, methods=['get'], url_path='served-cities')
    def served_cities(self, request):
        groups = CompanyRouteGroup.objects.filter(
            company__is_approved=True,
            company__is_rejected=False,
            company__user__is_active=True,
            destination__isnull=False,
        ).exclude(destination__city='')
        state = (request.query_params.get('state') or '').strip()
        if state:
            groups = groups.filter(destination__state__iexact=state)
        rows = (
            groups
            .values('destination__city', 'destination__state')
            .distinct()
            .order_by('destination__state', 'destination__city')
        )
        seen = set()
        cities = []
        for row in rows:
            city = row['destination__city'].strip()
            uf = row['destination__state'].strip().upper()
            key = (city.casefold(), uf)
            if not city or key in seen:
                continue
            seen.add(key)
            cities.append({'city': city, 'state': uf})
        return Response({'cities': cities})

    @extend_schema(
        methods=['GET'],
        tags=['Empresas'],
        summary='Consulte sua empresa',
        description='Somente titular autenticado; inclusive empresa ainda pendente de aprovação.',
        responses={200: CompanyListAndRetrieveSerializer},
    )
    @extend_schema(
        methods=['PATCH'],
        tags=['Empresas'],
        summary='Atualize sua empresa',
        description='Somente titular autenticado; não altera aprovação. Atualiza dados de perfil e endereço.',
        request=CompanyPatchSerializer,
        responses={200: CompanyListAndRetrieveSerializer},
    )
    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        company = get_object_or_404(Company, user=request.user)

        if request.method == 'PATCH':
            serializer = CompanyPatchSerializer(company, data=request.data, partial=True, context={'request': request})
            serializer.is_valid(raise_exception=True)
            company = serializer.save()

        serializer = CompanyListAndRetrieveSerializer(company, context=self.get_serializer_context())
        return Response(serializer.data)

    @extend_schema(
        tags=['Empresas'],
        summary='Consulte estatísticas da sua empresa',
        description='Apenas empresa titular aprovada; data local de atendimento e contagens por serviço concreto.',
        responses={
            200: inline_serializer(
                'CompanyStatistics',
                fields={
                    'routes_today': serializers.IntegerField(),
                    'date': serializers.DateField(),
                    'services': serializers.ListField(child=serializers.DictField()),
                },
            )
        },
    )
    @action(detail=False, methods=['get'], url_path='me/stats')
    def stats(self, request):
        company = get_object_or_404(companies_for(request.user))
        field = serializers.DateField()
        date = (
            field.run_validation(request.query_params['date'])
            if 'date' in request.query_params
            else timezone.localdate()
        )
        travels = Travel.objects.filter(company=company, service_day__date=date)
        services = list(
            travels
            .values('service', 'service__direction', 'service__target_time')
            .annotate(
                trips=Count('pk', distinct=True),
                allocated=Count('participations', filter=Q(participations__status='allocated')),
                on_board=Count('participations', filter=Q(participations__status='on_board')),
                dropped_off=Count('participations', filter=Q(participations__status='dropped_off')),
                no_show=Count('participations', filter=Q(participations__status='no_show')),
            )
            .order_by('service')
        )
        return Response({'date': date, 'routes_today': travels.count(), 'services': services})

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyCreateSerializer
        elif self.action == 'partial_update':
            return CompanyPatchSerializer
        return CompanyListAndRetrieveSerializer

    def get_queryset(self):
        queryset = Company.objects.select_related('user', 'user__profile_picture').order_by('trade_name', 'id')

        user = self.request.user

        if self.action != 'list' and user.is_authenticated:
            return queryset.filter(Q(is_approved=True, is_rejected=False, user__is_active=True) | Q(user=user))
        return queryset.filter(is_approved=True, is_rejected=False, user__is_active=True)

    def filter_queryset(self, queryset):
        if self.action != 'list':
            return super().filter_queryset(queryset)

        match_q, has_filter = build_route_group_match_q(self.request.query_params)
        if not has_filter:
            return queryset.none()

        matching_groups = CompanyRouteGroup.objects.select_related('destination').filter(match_q).order_by('name', 'id')
        queryset = queryset.filter(
            Exists(CompanyRouteGroup.objects.filter(company_id=OuterRef('pk')).filter(match_q))
        ).prefetch_related(Prefetch('route_groups', queryset=matching_groups, to_attr='matched_route_groups'))
        return super().filter_queryset(queryset)
