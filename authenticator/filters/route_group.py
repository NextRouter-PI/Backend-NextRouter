from django_filters import rest_framework as filters

from authenticator.models.company_route_group import CompanyRouteGroup


class CompanyRouteGroupFilter(filters.FilterSet):
    name = filters.CharFilter(field_name='name', lookup_expr='icontains')
    company = filters.NumberFilter(field_name='company_id')

    class Meta:
        model = CompanyRouteGroup
        fields = ('name', 'company')
