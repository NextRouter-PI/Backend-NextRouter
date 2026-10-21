from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from authenticator.models.company import Company
from authenticator.models.company_route_group import CompanyRouteGroup


class CompanyRouteGroupListAndRetrieveSerializer(ModelSerializer):
    passengers_count = serializers.SerializerMethodField()

    class Meta:
        model = CompanyRouteGroup
        fields = (
            'id',
            'company',
            'name',
            'common_cep',
            'reference_latitude',
            'reference_longitude',
            'passengers_count',
        )

    def get_passengers_count(self, obj):
        return obj.passengers.count()


class CompanyRouteGroupCreateSerializer(ModelSerializer):
    class Meta:
        model = CompanyRouteGroup
        fields = (
            'id',
            'name',
            'common_cep',
        )

    def validate_name(self, name):
        # A empresa não vem no corpo da requisição, então a restrição única (empresa, nome)
        # precisa ser checada aqui para não virar um IntegrityError (erro 500).
        if self.instance is not None:
            company_id = self.instance.company_id
        else:
            company_id = Company.objects.filter(user=self.context['request'].user).values_list('id', flat=True).first()

        queryset = CompanyRouteGroup.objects.filter(company_id=company_id, name__iexact=name)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('Sua empresa já possui um grupo de rota com este nome.')

        return name


class CompanyRouteGroupPatchSerializer(CompanyRouteGroupCreateSerializer):
    pass
