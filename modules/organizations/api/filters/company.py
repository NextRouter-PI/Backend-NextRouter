from django.db.models import Q
from django_filters import rest_framework as filters

from modules.organizations.models.company import Company


def build_route_group_match_q(params):
    """Retorna (Q, has_filter) para filtrar grupos de rota na descoberta pública."""
    query = Q()
    has_filter = False

    destination = (params.get('destination') or '').strip()
    if destination:
        has_filter = True
        query &= Q(name__icontains=destination) | Q(destination__name__icontains=destination)

    city = (params.get('city') or '').strip()
    if city:
        has_filter = True
        query &= Q(destination__city__iexact=city)

    state = (params.get('state') or '').strip()
    if state:
        has_filter = True
        query &= Q(destination__state__iexact=state)

    return query, has_filter


class CompanyFilter(filters.FilterSet):
    city = filters.CharFilter(method='noop_filter', label='Cidade atendida pelo grupo de rota')
    state = filters.CharFilter(method='noop_filter', label='UF atendida pelo grupo de rota')
    destination = filters.CharFilter(method='noop_filter', label='Nome do grupo de rota ou destino')
    ordering = filters.OrderingFilter(
        fields=(('trade_name', 'trade_name'),),
        field_labels={'trade_name': 'Nome da empresa'},
    )

    def noop_filter(self, queryset, name, value):
        # Aplicado de forma combinada no mesmo grupo de rota em CompanyViewSet.filter_queryset.
        return queryset

    class Meta:
        model = Company
        fields = ('city', 'state', 'destination')
