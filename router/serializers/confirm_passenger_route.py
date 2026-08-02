from rest_framework import serializers

from router.models.confirm_passenger_route import ConfirmPassengerRoute


class ConfirmPassengerRouteListAndRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfirmPassengerRoute
        fields = '__all__'


class ConfirmPassengerRoutePatchSerializer(serializers.ModelSerializer):
    confirm = serializers.BooleanField(required=True)

    class Meta:
        model = ConfirmPassengerRoute
        fields = ['confirm']

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError('Você deve aceitar/confirmar esta ação para prosseguir.')
        return value
