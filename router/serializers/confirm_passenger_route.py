from rest_framework import serializers

from router.models.confirm_passenger_route import ConfirmPassengerRoute


class ConfirmPassengerRouteListAndRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfirmPassengerRoute
        fields = '__all__'
