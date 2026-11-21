from rest_framework.serializers import ModelSerializer

from modules.accounts.api.serializers.user import UserReadSerializer
from modules.accounts.models import User
from modules.organizations.api.serializers.base import BaseProfileCreateSerializer, BaseProfilePatchSerializer
from modules.organizations.models.passenger import Passenger
from modules.uploads.api.serializers import ImageSerializer


class PassengerPublicUserSerializer(ModelSerializer):
    profile_picture_data = ImageSerializer(source='profile_picture', read_only=True)

    class Meta:
        model = User
        fields = (
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
        )


class PassengerPublicSerializer(ModelSerializer):
    user_data = PassengerPublicUserSerializer(source='user', read_only=True)

    class Meta:
        model = Passenger
        fields = ('id', 'user_data')


class PassengerListAndRetrieveSerializer(ModelSerializer):
    user_data = UserReadSerializer(source='user', read_only=True)

    class Meta:
        model = Passenger
        fields = (
            'id',
            'user_data',
        )

    def to_representation(self, instance):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and instance.user_id == user.pk:
            return super().to_representation(instance)
        return PassengerPublicSerializer(instance, context=self.context).data


class PassengerCreateSerializer(BaseProfileCreateSerializer):
    class Meta:
        model = Passenger
        fields = ('user_data',)

    def create(self, validated_data):
        return self.create_profile_for_user(Passenger, validated_data)


class PassengerPatchSerializer(BaseProfilePatchSerializer):
    class Meta:
        model = Passenger
        fields = ('user_data',)
