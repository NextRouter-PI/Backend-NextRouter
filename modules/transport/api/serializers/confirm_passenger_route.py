from django.db import transaction
from rest_framework import serializers

from modules.transport.models.confirm_passenger_route import ConfirmPassengerRoute
from modules.transport.models.travel import Travel


class ConfirmPassengerRouteListAndRetrieveSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_address = serializers.SerializerMethodField()

    class Meta:
        model = ConfirmPassengerRoute
        fields = '__all__'

    def get_user_address(self, obj) -> str:
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

        if travel.status not in {Travel.Status.SCHEDULED, Travel.Status.IN_PROGRESS}:
            raise serializers.ValidationError('Esta viagem não está aceitando confirmações.')

        if user.is_staff or user.is_superuser:
            return travel

        is_participant = travel.path.route_group.passengers.filter(user=user, is_approved=True).exists()
        if not is_participant:
            raise serializers.ValidationError('Você não faz parte do grupo de rota desta viagem.')

        return travel

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        travel = Travel.objects.select_for_update().get(pk=validated_data['travel'].pk)
        self.validate_travel(travel)
        confirmation, _created = ConfirmPassengerRoute.objects.update_or_create(
            travel=travel,
            user=user,
            defaults={'confirm': validated_data.get('confirm', True)},
        )
        return confirmation
