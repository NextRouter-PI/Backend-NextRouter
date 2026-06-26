from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models import User
from uploader.models import Image
from uploader.serializers import ImageSerializer, ImageUploadSerializer


class UserListAndRetriveSerializer(ModelSerializer):
    profile_picture_data = ImageSerializer(source='profile_picture')

    class Meta:
        model = User
        fields = ['id', 'name', 'profile_picture_data', 'cep']


class UserCreateSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    cep = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    cpf = serializers.CharField(required=True)
    profile_picture = ImageUploadSerializer('profile_picture', required=False)

    def validate_password(self, value):
        try:
            validate_password(value, user=None)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        profile_picture_data = validated_data.pop('profile_picture', None)
        user_name = validated_data.get('name', '')
        user_cpf = validated_data.get('cpf', '')

        pic_instance = None

        if profile_picture_data:
            profile_picture_data['description'] = f'Foto de {user_name} ({user_cpf})'

            pic_instance = Image.objects.create(**profile_picture_data)

        return User.objects.create_user(**validated_data, profile_picture=pic_instance)

    class Meta:
        model = User
        fields = ['email', 'name', 'password', 'cep', 'phone', 'profile_picture', 'cpf', 'birthday']


class UserPatchSerializer(UserCreateSerializer):
    class Meta:
        model = User
        fields = ['email', 'name', 'cep', 'phone', 'profile_picture']
