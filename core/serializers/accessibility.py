from rest_framework.serializers import ModelSerializer

from core.models import Accessibility


class AccessibilitySerializer(ModelSerializer):
    class Meta:
        model = Accessibility
        fields = '__all__'
