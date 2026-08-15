from django.db import transaction
from rest_framework.serializers import ModelSerializer, SlugRelatedField

from authenticator.mixins.route_group import GroupRouteForbiddenValidatorMixin
from authenticator.models.driver import Driver
from authenticator.serializers.user import (
    BaseProfileCreateSerializer,
    BaseProfilePatchSerializer,
    UserListAndRetriveSerializer,
)
from uploader.models.document import Document


class DriverListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)

    class Meta:
        model = Driver
        fields = (
            'user_data',
            # 'is_approved',
            'route_group',
        )
        read_only_fields = ('route_group',)


class DriverCreateSerializer(BaseProfileCreateSerializer):
    cnh = SlugRelatedField(
        slug_field='attachment_key',
        queryset=Document.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Driver
        fields = (
            'user_data',
            'cnh',
        )

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = self.create_user_instance(user_data)
        return Driver.objects.create(user=user, **validated_data)


class DriverPatchSerializer(GroupRouteForbiddenValidatorMixin, BaseProfilePatchSerializer):
    cnh = SlugRelatedField(
        slug_field='attachment_key',
        queryset=Document.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Driver
        fields = ('user_data', 'cnh', 'route_group')
