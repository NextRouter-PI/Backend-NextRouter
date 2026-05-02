from rest_framework.serializers import ModelSerializer

from core.models.passenger import Passenger


class PassengerSerializer(ModelSerializer):
    class Meta:
        model = Passenger
        fields = '__all__'
