from rest_framework.serializers import ModelSerializer

from authenticator.models.company import Company
from authenticator.models.company_route_group import CompanyRouteGroup


class CompanyRouteGroupListAndRetrieveSerializer(ModelSerializer):
    class Meta:
        model = CompanyRouteGroup
        fields = (
            'name',
            'common_cep',
        )


class CompanyRouteGroupCreateSerializer(ModelSerializer):
    # Cria o grupo de rotas com relacionado ao usuário que fez a requisição.
    def perform_create(self, serializer):
        company = Company.objects.get(user=self.request.user)
        serializer.save(company=company)

    class Meta:
        model = CompanyRouteGroup
        fields = (
            'name',
            'common_cep',
        )


class CompanyRouteGroupPatchSerializer(ModelSerializer):
    class Meta:
        model = CompanyRouteGroup
        fields = (
            'name',
            'common_cep',
        )
