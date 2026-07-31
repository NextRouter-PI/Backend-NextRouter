from django.db import transaction
from rest_framework.serializers import ModelSerializer

from core.models.driver import Driver
from core.serializers.user import BaseProfileCreateSerializer, BaseProfilePatchSerializer, UserListAndRetriveSerializer
from uploader.models.document import Document
from uploader.serializers.document import DocumentUploadSerializer


class DriverListAndRetrieveSerializer(ModelSerializer):
    user_data = UserListAndRetriveSerializer(source='user', read_only=True)

    class Meta:
        model = Driver
        fields = ['user_data', 'is_approved', 'cnh']


class DriverCreateSerializer(BaseProfileCreateSerializer):
    cnh = DocumentUploadSerializer()

    class Meta:
        model = Driver
        fields = ['user_data', 'cnh']

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        cnh_data = validated_data.pop('cnh')

        user = self.create_user_instance(user_data)
        cnh_object = Document.objects.create(**cnh_data)

        return Driver.objects.create(user=user, cnh=cnh_object, **validated_data)


class DriverPatchSerializer(BaseProfilePatchSerializer):
    class Meta:
        model = Driver
        fields = ['user_data']
