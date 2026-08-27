from rest_framework import serializers

from router.models.confirm_passenger_route import ConfirmPassengerRoute


class ConfirmPassengerRouteListAndRetrieveSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_address = serializers.SerializerMethodField()

    class Meta:
        model = ConfirmPassengerRoute
        fields = '__all__'

    def get_user_address(self, obj):
        user = obj.user
        parts = [part for part in (user.street, user.number, user.neighborhood, user.city, user.state) if part]
        return ', '.join(parts) if parts else ''


class ConfirmPassengerRouteCreateSerializer(serializers.ModelSerializer):
    """
    Cria (ou atualiza, caso já exista) a confirmação de presença do usuário autenticado
    para a viagem informada. Usado pelo questionário diário de confirmação de presença.
    """

    class Meta:
        model = ConfirmPassengerRoute
        fields = ('id', 'travel', 'confirm')
        read_only_fields = ('id',)

    def validate_travel(self, travel):
        user = self.context['request'].user

        if user.is_staff or user.is_superuser:
            return travel

        is_participant = travel.path.route_group.passengers.filter(user=user).exists()
        if not is_participant:
            raise serializers.ValidationError('Você não faz parte do grupo de rota desta viagem.')

        return travel

    def create(self, validated_data):
        user = self.context['request'].user
        confirmation, _created = ConfirmPassengerRoute.objects.update_or_create(
            travel=validated_data['travel'],
            user=user,
            defaults={'confirm': validated_data.get('confirm', True)},
        )
        return confirmation
