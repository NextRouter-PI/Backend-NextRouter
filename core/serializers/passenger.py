from rest_framework.serializers import ModelSerializer

from core.models import Passenger


class PassengerSerializer(ModelSerializer):
    class Meta:
        model = Passenger
        fields = '__all__'
