from django.db import transaction
from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField, Serializer

from authenticator.mixins.route_group import GroupRouteForbiddenValidatorMixin
from authenticator.models.company_route_group import CompanyRouteGroup
from authenticator.models.passenger import Passenger
from authenticator.serializers.user import (
    BaseProfileCreateSerializer,
    BaseProfilePatchSerializer,
    UserListAndRetriveSerializer,
)


class PassengerListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)

    class Meta:
        model = Passenger
        fields = (
            'id',
            'user_data',
            # 'is_approved',
            'route_group',
        )
        read_only_fields = ('route_group',)


class PassengerCreateSerializer(BaseProfileCreateSerializer):
    class Meta:
        model = Passenger
        fields = ('user_data',)

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = self.create_user_instance(user_data)
        return Passenger.objects.create(user=user, **validated_data)


class PassengerPatchSerializer(GroupRouteForbiddenValidatorMixin, BaseProfilePatchSerializer):
    class Meta:
        model = Passenger
        fields = ('user_data', 'route_group')


class PassengerRouteGroupRequestSerializer(Serializer):
    route_group = PrimaryKeyRelatedField(queryset=CompanyRouteGroup.objects.all())
