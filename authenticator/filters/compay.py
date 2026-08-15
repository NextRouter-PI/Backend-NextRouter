from django_filters import rest_framework as filters

from authenticator.models.company import Company


class CompanyFilter(filters.FilterSet):
    user__name = filters.CharFilter(field_name='user__name', lookup_expr='icontains')
    trade_name = filters.CharFilter(field_name='trade_name', lookup_expr='icontains')

    class Meta:
        model = Company
        fields = ('trade_name', 'state_registration', 'user__name')
