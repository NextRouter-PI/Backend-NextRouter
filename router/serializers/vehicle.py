from rest_framework import serializers

from authenticator.models.company_route_group import CompanyRouteGroup
from router.models.vehicle import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            'id',
            'route_group',
            'garage_cep',
            'plate',
        )


class VehicleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            'id',
            'route_group',
            'garage_cep',
            'plate',
        )


class VehiclePatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            'id',
            'route_group',
            'garage_cep',
            'plate',
        )
