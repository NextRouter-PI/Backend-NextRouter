from rest_framework import serializers

from router.models.travel import Travel
from router.serializers.ownership import validate_driver_in_route_group, validate_route_group_ownership


class TravelListAndRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Travel
        fields = (
            'id',
            'company',
            'driver',
            'path',
            'status',
            'started_at',
            'finished_at',
            'current_latitude',
            'current_longitude',
            'location_updated_at',
        )
        read_only_fields = (
            'company',
            'driver',
            'path',
            'status',
            'started_at',
            'finished_at',
            'current_latitude',
            'current_longitude',
            'location_updated_at',
        )


class TravelCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Travel
        fields = (
            'id',
            'company',
            'driver',
            'path',
        )
        # A empresa da viagem é sempre a dona do trajeto (definida na view), nunca enviada pelo cliente.
        read_only_fields = ('company',)

    def validate_path(self, path):
        validate_route_group_ownership(self.context, path.route_group)
        return path

    def validate(self, attrs):
        path = attrs.get('path', getattr(self.instance, 'path', None))
        driver = attrs.get('driver', getattr(self.instance, 'driver', None))

        if path is not None:
            validate_driver_in_route_group(driver, path.route_group)

        return attrs


class TravelLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
