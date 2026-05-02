from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models import User


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'is_active', 'is_staff', 'is_superuser', 'groups']


class UserRegistrationSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    cep = serializers.CharField(write_only=True, required=False)
    phone = serializers.CharField(write_only=True, required=False)
    profile_picture = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['email', 'name', 'password', 'cep', 'phone', 'profile_picture']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

    def validate_password(self, value):
        try:
            validate_password(value, user=None)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
