from rest_framework import serializers

from modules.transport.models import Vehicle
from shared.api import InputModelSerializer


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            'id',
            'company',
            'plate',
            'vehicle_type',
            'brand',
            'model',
            'year',
            'seats',
            'capacity',
            'status',
            'garage_point',
            'color',
            'features',
            'notes',
        )


class VehicleInput(InputModelSerializer):
    garage_point_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    class Meta:
        model = Vehicle
        fields = (
            'plate',
            'vehicle_type',
            'brand',
            'model',
            'year',
            'seats',
            'capacity',
            'status',
            'garage_point_id',
            'color',
            'features',
            'notes',
        )
