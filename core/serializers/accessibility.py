from rest_framework import serializers

from core.models import Accessibility


class AccessibilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Accessibility
        fields = '__all__'
