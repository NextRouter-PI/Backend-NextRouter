from modules.transport.api.serializers.configuration import PolicySerializer
from modules.transport.models import ResponsePolicy
from shared.domain_api import domain_resource

from .base import ConfigurationViewSet


@domain_resource('Configuração', 'políticas de resposta')
class PolicyViewSet(ConfigurationViewSet):
    company_lookup = 'route_group__company'
    queryset = ResponsePolicy.objects.none()
    serializer_class = PolicySerializer
    filterset_fields = ('route_group',)
