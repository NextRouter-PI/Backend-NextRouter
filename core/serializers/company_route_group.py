from rest_framework.serializers import ModelSerializer

from core.models.company_route_group import CompanyRouteGroup


class CompanyRouteGroupSerializer(ModelSerializer):
    class Meta:
        model = CompanyRouteGroup
        fields = ['name', 'commom_adress']
