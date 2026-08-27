from rest_framework import serializers

from authenticator.models.driver_rating import DriverRating


class DriverRatingListAndRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverRating
        fields = (
            'id',
            'driver',
            'passenger',
            'travel',
            'score',
            'comment',
            'created_at',
        )
        read_only_fields = ('passenger', 'created_at')


class DriverRatingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverRating
        fields = (
            'id',
            'driver',
            'travel',
            'score',
            'comment',
        )

    def validate(self, attrs):
        request = self.context['request']
        travel = attrs.get('travel')
        driver = attrs.get('driver')

        if travel and travel.driver_id != driver.id:
            raise serializers.ValidationError({'travel': 'Esta viagem não foi realizada por este motorista.'})

        if travel and not travel.passenger_confirms.filter(user=request.user).exists():
            raise serializers.ValidationError({'travel': 'Você não participou desta viagem.'})

        return attrs

    def create(self, validated_data):
        validated_data['passenger'] = self.context['request'].user
        return super().create(validated_data)
