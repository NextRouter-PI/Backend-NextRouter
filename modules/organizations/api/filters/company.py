from django.db.models import Q
from django_filters import rest_framework as filters

from modules.organizations.models.company import Company


class CompanyFilter(filters.FilterSet):
    trade_name = filters.CharFilter(field_name='trade_name', lookup_expr='icontains')
    city = filters.CharFilter(field_name='route_groups__destination__city', lookup_expr='iexact', distinct=True)
    state = filters.CharFilter(field_name='route_groups__destination__state', lookup_expr='iexact', distinct=True)
    destination = filters.CharFilter(method='filter_destination')

    def filter_destination(self, queryset, name, value):
        return queryset.filter(
            Q(route_groups__name__icontains=value) | Q(route_groups__destination__name__icontains=value)
        ).distinct()

    class Meta:
        model = Company
        fields = ('trade_name', 'city', 'state', 'destination')
