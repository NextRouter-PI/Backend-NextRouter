from rest_framework import serializers

from core.models import Profile

from .accessibility import AccessibilitySerializer


class ProfileSerializer(serializers.ModelSerializer):
    accessibility = AccessibilitySerializer(read_only=True)

    class Meta:
        model = Profile
        fields = '__all__'
