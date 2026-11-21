from django.db import transaction
from django.db.models import Avg
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SlugRelatedField

from modules.accounts.api.serializers.user import UserListAndRetriveSerializer
from modules.organizations.api.serializers.base import BaseProfileCreateSerializer, BaseProfilePatchSerializer
from modules.organizations.models.driver import Driver
from modules.uploads.api.serializers.document import DocumentSerializer
from modules.uploads.models.document import Document


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
            'average_rating',
            'ratings_count',
            'cnh_data',
        )

    def get_average_rating(self, obj) -> float | None:
        average = getattr(obj, '_average_rating', None)
        if average is None and not hasattr(obj, '_average_rating'):
            average = obj.ratings.aggregate(average=Avg('score'))['average']
        return round(average, 1) if average is not None else None

    def get_ratings_count(self, obj) -> int:
        count = getattr(obj, '_ratings_count', None)
        if count is not None:
            return count
        return obj.ratings.count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and instance.user_id == user.pk:
            return data
        data['user_data'] = {key: data['user_data'][key] for key in ('id', 'name')}
        data.pop('cnh_data', None)
        return data


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


class DriverPatchSerializer(BaseProfilePatchSerializer):
    cnh = SlugRelatedField(
        slug_field='attachment_key',
        queryset=Document.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Driver
        fields = ('user_data', 'cnh')
