from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

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


class CompanyRouteGroupPatchSerializer(ModelSerializer):
    class Meta:
        model = CompanyRouteGroup
        fields = (
            'id',
            'name',
            'common_cep',
        )
