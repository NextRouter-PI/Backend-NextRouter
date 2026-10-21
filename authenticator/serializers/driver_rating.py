from rest_framework import serializers

from authenticator.models.driver_rating import DriverRating
from router.models.travel import Travel


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
    # Obrigatória: só quem viajou pode avaliar, uma única vez por viagem.
    travel = serializers.PrimaryKeyRelatedField(queryset=Travel.objects.all())

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
        user = self.context['request'].user
        travel = attrs['travel']
        driver = attrs['driver']

        if travel.driver_id != driver.id:
            raise serializers.ValidationError({'travel': 'Esta viagem não foi realizada por este motorista.'})

        if travel.status != Travel.Status.FINISHED:
            raise serializers.ValidationError({'travel': 'Só é possível avaliar viagens finalizadas.'})

        if not travel.passenger_confirms.filter(user=user).exists():
            raise serializers.ValidationError({'travel': 'Você não participou desta viagem.'})

        if DriverRating.objects.filter(driver=driver, passenger=user, travel=travel).exists():
            raise serializers.ValidationError({'travel': 'Você já avaliou este motorista nesta viagem.'})

        return attrs

    def create(self, validated_data):
        validated_data['passenger'] = self.context['request'].user
        return super().create(validated_data)
