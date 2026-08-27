from django.db import transaction
from django.db.models import Avg
from rest_framework.serializers import ModelSerializer, SlugRelatedField

from authenticator.mixins.route_group import GroupRouteForbiddenValidatorMixin
from authenticator.models.driver import Driver
from authenticator.serializers.user import (
    BaseProfileCreateSerializer,
    BaseProfilePatchSerializer,
    UserListAndRetriveSerializer,
)
from rest_framework import serializers
from uploader.models.document import Document
from uploader.serializers.document import DocumentSerializer


class DriverListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)
    average_rating = serializers.SerializerMethodField()
    ratings_count = serializers.SerializerMethodField()
    cnh_data = DocumentSerializer(source='cnh', read_only=True)

    class Meta:
        model = Driver
        fields = (
            'id',
            'user_data',
            # 'is_approved',
            'route_group',
            'average_rating',
            'ratings_count',
            'cnh_data',
        )
        read_only_fields = ('route_group',)

    def get_average_rating(self, obj):
        average = obj.ratings.aggregate(average=Avg('score'))['average']
        return round(average, 1) if average is not None else None

    def get_ratings_count(self, obj):
        return obj.ratings.count()


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
