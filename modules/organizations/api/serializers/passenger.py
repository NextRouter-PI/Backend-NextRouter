from django.db import transaction
from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField, Serializer

from modules.accounts.api.serializers.user import (
    BaseProfileCreateSerializer,
    BaseProfilePatchSerializer,
    UserListAndRetriveSerializer,
)
from modules.organizations.mixins.is_approved import clear_approval_notification_key
from modules.organizations.mixins.route_group import GroupRouteForbiddenValidatorMixin
from modules.organizations.models.company_route_group import CompanyRouteGroup
from modules.organizations.models.passenger import Passenger


class PassengerListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)

    class Meta:
        model = Passenger
        fields = (
            'id',
            'user_data',
            'route_group',
            'review_status',
        )
        read_only_fields = ('route_group',)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and (user.is_staff or user.is_superuser or instance.user_id == user.pk):
            return data
        fields = {'id', 'name'}
        if (
            user
            and instance.route_group
            and instance.route_group.company.is_approved
            and instance.route_group.company.user_id == user.pk
        ):
            fields.update(('street', 'number', 'neighborhood', 'city', 'state', 'cep', 'latitude', 'longitude'))
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


class PassengerPatchSerializer(GroupRouteForbiddenValidatorMixin, BaseProfilePatchSerializer):
    class Meta:
        model = Passenger
        fields = ('user_data', 'route_group')

    @transaction.atomic
    def update(self, instance, validated_data):
        old_group_id = instance.route_group_id
        if 'route_group' in validated_data and validated_data['route_group'] != instance.route_group:
            validated_data['is_approved'] = False
            validated_data['is_rejected'] = False
            clear_approval_notification_key(instance, old_group_id)
        return super().update(instance, validated_data)


class PassengerRouteGroupRequestSerializer(Serializer):
    route_group = PrimaryKeyRelatedField(queryset=CompanyRouteGroup.objects.filter(company__is_approved=True))
