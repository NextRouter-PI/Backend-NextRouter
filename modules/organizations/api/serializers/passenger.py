from django.db import transaction
from rest_framework.serializers import ModelSerializer

from modules.accounts.api.serializers.user import UserListAndRetriveSerializer
from modules.organizations.api.serializers.base import BaseProfileCreateSerializer, BaseProfilePatchSerializer
from modules.organizations.models.passenger import Passenger


class PassengerListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)

    class Meta:
        model = Passenger
        fields = (
            'id',
            'user_data',
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and instance.user_id == user.pk:
            return data
        fields = {
            'id',
            'name',
            'phone',
            'profile_picture_data',
            'cep',
            'street',
            'number',
            'complement',
            'neighborhood',
            'city',
            'state',
            'latitude',
            'longitude',
        }
        data['user_data'] = {key: value for key, value in data['user_data'].items() if key in fields}
        return data


class PassengerCreateSerializer(BaseProfileCreateSerializer):
    class Meta:
        model = Passenger
        fields = ('user_data',)

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = self.create_user_instance(user_data)
        return Passenger.objects.create(user=user, **validated_data)


class PassengerPatchSerializer(BaseProfilePatchSerializer):
    class Meta:
        model = Passenger
        fields = ('user_data',)
