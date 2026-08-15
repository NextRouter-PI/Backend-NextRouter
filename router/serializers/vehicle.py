from rest_framework import serializers

from router.models.vehicle import Vehicle


class VehicleListAndRetrieveSerializer(serializers.ModelSerializer):
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
