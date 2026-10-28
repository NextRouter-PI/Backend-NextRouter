from django.db import transaction
from django.db.models import Avg
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField, Serializer, SlugRelatedField

from modules.accounts.api.serializers.user import (
    BaseProfileCreateSerializer,
    BaseProfilePatchSerializer,
    UserListAndRetriveSerializer,
)
from modules.organizations.mixins.is_approved import clear_approval_notification_key
from modules.organizations.mixins.route_group import GroupRouteForbiddenValidatorMixin
from modules.organizations.models.company_route_group import CompanyRouteGroup
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
            'route_group',
            'review_status',
            'average_rating',
            'ratings_count',
            'cnh_data',
        )
        read_only_fields = ('route_group',)

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
        if user and (user.is_staff or user.is_superuser or instance.user_id == user.pk):
            return data
        data['user_data'] = {key: data['user_data'][key] for key in ('id', 'name')}
        if not (
            user
            and instance.route_group
            and instance.route_group.company.is_approved
            and instance.route_group.company.user_id == user.pk
        ):
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

    @transaction.atomic
    def update(self, instance, validated_data):
        old_group_id = instance.route_group_id
        group_changing = 'route_group' in validated_data and validated_data['route_group'] != instance.route_group
        if group_changing:
            validated_data['is_approved'] = False
            validated_data['is_rejected'] = False
            clear_approval_notification_key(instance, old_group_id)
        updated = super().update(instance, validated_data)
        if group_changing and old_group_id:
            from modules.transport.models.vehicle import Vehicle

            Vehicle.objects.filter(driver=updated, route_group_id=old_group_id).update(driver=None)
        return updated


class DriverRouteGroupRequestSerializer(Serializer):
    route_group = PrimaryKeyRelatedField(queryset=CompanyRouteGroup.objects.filter(company__is_approved=True))
