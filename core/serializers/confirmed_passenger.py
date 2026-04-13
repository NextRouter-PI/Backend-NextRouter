from rest_framework.serializers import ModelSerializer

from core.models import Confirmed_Passenger


class Confirmed_PassengerSerializer(ModelSerializer):
    class Meta:
        model = Confirmed_Passenger
        fields = '__all__'
