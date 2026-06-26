from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models.driver import Driver
from core.models.user import User
from core.serializers.user import UserCreateSerializer, UserPatchSerializer
from uploader.models.document import Document
from uploader.serializers.document import DocumentUploadSerializer


class DriverListAndRetrieveSerializer(ModelSerializer):
    driver_id = serializers.IntegerField(source='user.id', read_only=True)
    name = serializers.CharField(source='user.name', read_only=True)
    profile_picture = serializers.ImageField(source='user.profile_picture', read_only=True)
    cep = serializers.CharField(source='user.cep', read_only=True)

    class Meta:
        model = Driver
        fields = ['id', 'driver_id', 'name', 'profile_picture', 'cep', 'is_approved', 'cnh']


class DriverCreateSerializer(ModelSerializer):
    user_data = UserCreateSerializer(source='user')
    cnh = DocumentUploadSerializer()

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        cnh_data = validated_data.pop('cnh')
        cnh_object = Document.objects.create(**cnh_data)
        user = User.objects.create_user(**user_data)
        driver = Driver.objects.create(
            user=user,
            cnh=cnh_object,
            **validated_data,
        )
        return driver

    class Meta:
        model = Driver
        fields = ['user_data', 'cnh']


class DriverPatchSerializer(ModelSerializer):
    user_data = UserPatchSerializer(source='user', required=False)

    class Meta:
        model = Driver
        fields = ['user_data']

    def validate(self, attrs):

        forbidden_fields = ['is_approved', 'group_route', 'user']
        errors = {}

        for field in forbidden_fields:
            if field in self.initial_data:
                errors[field] = f"Você não tem permissão para alterar o campo '{field}'."

        if 'user_data' in self.initial_data and 'cpf' in self.initial_data['user_data']:
            raise serializers.ValidationError({'user_data': {'cpf': 'O CPF não pode ser alterado após a criação.'}})

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user_instance = instance.user
            for attr, value in user_data.items():
                setattr(user_instance, attr, value)
            user_instance.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
