from django.db import IntegrityError, transaction
from rest_framework import serializers

from modules.organizations.models.driver import Driver
from modules.transport.models.driver_rating import MAX_SCORE, MIN_SCORE, DriverRating
from modules.transport.models.travel import Travel


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
    travel = serializers.PrimaryKeyRelatedField(queryset=Travel.objects.select_related('driver'))
    driver = serializers.PrimaryKeyRelatedField(queryset=Driver.objects.all(), required=False)
    score = serializers.IntegerField(min_value=MIN_SCORE, max_value=MAX_SCORE)

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
        driver = attrs.get('driver') or travel.driver
        attrs['driver'] = driver

        if travel.driver_id != driver.id:
            raise serializers.ValidationError({'travel': 'Esta viagem não foi realizada por este motorista.'})

        if travel.status != Travel.Status.FINISHED:
            raise serializers.ValidationError({'travel': 'Só é possível avaliar viagens finalizadas.'})

        if not travel.passenger_confirms.filter(user=user, confirm=True).exists():
            raise serializers.ValidationError({'travel': 'Você não participou desta viagem.'})

        if DriverRating.objects.filter(passenger=user, travel=travel).exists():
            raise serializers.ValidationError({'travel': 'Você já avaliou este motorista nesta viagem.'})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        travel = Travel.objects.select_for_update().get(pk=validated_data['travel'].pk)
        if travel.status != Travel.Status.FINISHED:
            raise serializers.ValidationError({'travel': 'Só é possível avaliar viagens finalizadas.'})
        if DriverRating.objects.filter(passenger=user, travel=travel).exists():
            raise serializers.ValidationError({'travel': 'Você já avaliou este motorista nesta viagem.'})
        validated_data['passenger'] = user
        try:
            return super().create(validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError({'travel': 'Você já avaliou este motorista nesta viagem.'}) from exc
