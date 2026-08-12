from rest_framework.serializers import ModelSerializer

from authenticator.models.company_route_group import CompanyRouteGroup


class CompanyRouteGroupSerializer(ModelSerializer):
    class Meta:
        model = CompanyRouteGroup
        fields = (
            'name',
            'common_cep',
        )
