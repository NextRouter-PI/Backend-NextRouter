from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models.passenger import Passenger
from core.models.user import User
from core.serializers.user import UserCreateSerializer, UserPatchSerializer


class PassengerListAndRetrieveSerializer(ModelSerializer):
    passenger_id = serializers.IntegerField(source='user.id')
    name = serializers.CharField(source='user.name')
    profile_picture = serializers.ImageField(source='user.profile_picture')
    cep = serializers.CharField(source='user.cep')

    class Meta:
        model = Passenger
        fields = ['passenger_id', 'name', 'profile_picture', 'cep']


class PassengerCreateSerializer(ModelSerializer):
    user_data = UserCreateSerializer(source='user')

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create_user(**user_data)
        passenger = Passenger.objects.create(
            user=user,
            **validated_data,
        )
        return passenger

    class Meta:
        model = Passenger
        fields = ['user_data', 'group_route']


class PassengerPatchSerializer(UserPatchSerializer):
    class Meta:
        model = User
        fields = '__all__'
