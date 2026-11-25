from django.db.models import Avg
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SlugRelatedField

from modules.accounts.api.serializers.user import UserReadSerializer
from modules.accounts.models import User
from modules.organizations.api.serializers.base import BaseProfileCreateSerializer, BaseProfilePatchSerializer
from modules.organizations.models.driver import Driver
from modules.uploads.api.serializers.document import DocumentSerializer
from modules.uploads.models.document import Document


class DriverPublicUserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'name')


class _DriverRatingMixin(serializers.Serializer):
    average_rating = serializers.SerializerMethodField()
    ratings_count = serializers.SerializerMethodField()

    def get_average_rating(self, obj) -> float | None:
        if hasattr(obj, '_average_rating'):
            average = obj._average_rating
        else:
            average = obj.ratings.aggregate(average=Avg('score'))['average']
        return round(average, 1) if average is not None else None

    def get_ratings_count(self, obj) -> int:
        if hasattr(obj, '_ratings_count'):
            return obj._ratings_count
        return obj.ratings.count()


class DriverPublicSerializer(_DriverRatingMixin, ModelSerializer):
    user_data = DriverPublicUserSerializer(source='user', read_only=True)

    class Meta:
        model = Driver
        fields = ('id', 'user_data', 'average_rating', 'ratings_count')


class DriverListAndRetrieveSerializer(_DriverRatingMixin, ModelSerializer):
    user_data = UserReadSerializer(source='user', read_only=True)
    cnh_data = DocumentSerializer(source='cnh', read_only=True)

    class Meta:
        model = Driver
        fields = (
            'id',
            'user_data',
            'average_rating',
            'ratings_count',
            'cnh_data',
            'location_consent_at',
        )
        read_only_fields = ('location_consent_at',)

    def to_representation(self, instance):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and instance.user_id == user.pk:
            return super().to_representation(instance)
        return DriverPublicSerializer(instance, context=self.context).data


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

    def create(self, validated_data):
        return self.create_profile_for_user(Driver, validated_data)


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


class LocationConsentInput(serializers.Serializer):
    consent = serializers.BooleanField()
