from django.db import transaction
from rest_framework.serializers import ModelSerializer

from core.models.passenger import Passenger
from core.serializers.user import BaseProfileCreateSerializer, BaseProfilePatchSerializer, UserListAndRetriveSerializer


class PassengerListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)

    class Meta:
        model = Passenger
        fields = ['id', 'user_data', 'is_approved', 'group_route']


class PassengerCreateSerializer(BaseProfileCreateSerializer):
    class Meta:
        model = Passenger
        fields = ['user_data']

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = self.create_user_instance(user_data)
        return Passenger.objects.create(user=user, **validated_data)


class PassengerPatchSerializer(BaseProfilePatchSerializer):
    class Meta:
        model = Passenger
        fields = ['user_data']
