from django.db.models import Exists, OuterRef, Prefetch
from django_filters import rest_framework as filters

from modules.organizations.models.company import Company
from modules.organizations.models.company_route_group import CompanyRouteGroup


def _extract_discovery_params(params) -> dict[str, str]:
    return {
        'city': (params.get('city') or '').strip(),
        'state': (params.get('state') or '').strip(),
        'destination': (params.get('destination') or '').strip(),
    }


class CompanyFilter(filters.FilterSet):
    city = filters.CharFilter(method='noop_filter', label='Cidade atendida pelo grupo de rota')
    state = filters.CharFilter(method='noop_filter', label='UF atendida pelo grupo de rota')
    destination = filters.CharFilter(method='noop_filter', label='Nome do grupo de rota ou destino')
    ordering = filters.OrderingFilter(
        fields=(('trade_name', 'trade_name'),),
        field_labels={'trade_name': 'Nome da empresa'},
    )

    def noop_filter(self, queryset, name, value):
        return queryset

    def filter_queryset(self, queryset):
        # Na listagem pública, exige ao menos um filtro de grupo de rota combinado no mesmo grupo.
        criteria = _extract_discovery_params(self.data)
        if not any(criteria.values()):
            return queryset.none()
        matching_groups = (
            CompanyRouteGroup.objects
            .select_related('destination')
            .matching_discovery(**criteria)
            .order_by('name', 'id')
        )
        queryset = queryset.filter(
            Exists(CompanyRouteGroup.objects.filter(company_id=OuterRef('pk')).matching_discovery(**criteria))
        ).prefetch_related(Prefetch('route_groups', queryset=matching_groups, to_attr='matched_route_groups'))
        return super().filter_queryset(queryset)

    class Meta:
        model = Company
        fields = ('city', 'state', 'destination')
