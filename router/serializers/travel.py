from rest_framework import serializers

from router.models.travel import Travel


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

    def validate(self, attrs):
        driver = attrs.get('driver')
        path = attrs.get('path')

        if driver and path and driver.route_group_id != path.route_group_id:
            raise serializers.ValidationError(
                {'driver': 'O motorista não pertence ao grupo de rota deste trajeto.'}
            )

        return attrs


class TravelLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
