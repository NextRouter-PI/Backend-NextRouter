from rest_framework import serializers

from modules.transport.models import DriverInvitation
from shared.api import InputSerializer


class InvitationSerializer(serializers.ModelSerializer):
    planned_start = serializers.DateTimeField(source='travel.planned_start', read_only=True)
    planned_end = serializers.DateTimeField(source='travel.planned_end', read_only=True)

    class Meta:
        model = DriverInvitation
        fields = (
            'id',
            'travel',
            'driver_membership',
            'planned_start',
            'planned_end',
            'created_at',
            'expires_at',
            'is_current',
            'status',
            'responded_at',
            'closed_at',
        )


class InviteInput(InputSerializer):
    driver_membership_id = serializers.IntegerField(min_value=1)
    expires_at = serializers.DateTimeField()


class InviteResponseInput(InputSerializer):
    accept = serializers.BooleanField()
