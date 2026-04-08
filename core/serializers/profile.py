from rest_framework.serializers import ModelSerializer

from core.models import Profile

from .accessibility import AccessibilitySerializer


class ProfileSerializer(ModelSerializer):
    accessibility = AccessibilitySerializer(read_only=True)

    class Meta:
        model = Profile
        fields = '__all__'
