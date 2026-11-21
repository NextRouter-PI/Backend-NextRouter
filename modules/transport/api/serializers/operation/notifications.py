from rest_framework import serializers

from modules.transport.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'kind', 'resource_type', 'resource_id', 'payload', 'created_at', 'read_at')
