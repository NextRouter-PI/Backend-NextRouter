from rest_framework import serializers

from router.models.vehicle import Vehicle


class VehicleListAndRetrieveSerializer(serializers.ModelSerializer):
    driver_name = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = (
            'id',
            'route_group',
            'garage_cep',
            'plate',
            'model',
            'year',
            'capacity',
            'status',
            'color',
            'features',
            'driver',
            'driver_name',
        )

    def get_driver_name(self, obj):
        return obj.driver.user.name.title() if obj.driver else None


class VehicleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            'id',
            'route_group',
            'garage_cep',
            'plate',
            'model',
            'year',
            'capacity',
            'status',
            'color',
            'features',
            'driver',
        )


class VehiclePatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            'id',
            'route_group',
            'garage_cep',
            'plate',
            'model',
            'year',
            'capacity',
            'status',
            'color',
            'features',
            'driver',
        )
