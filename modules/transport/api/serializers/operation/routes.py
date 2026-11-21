from rest_framework import serializers

from modules.transport.api.serializers.common import user_avatar_url
from modules.transport.models import (
    RouteOptimizationJob,
    RouteSnapshot,
    RouteStop,
    RouteStopParticipant,
    TravelPublication,
)
from shared.api import InputSerializer


class SnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteSnapshot
        fields = (
            'id',
            'travel',
            'revision',
            'base_revision',
            'change_request',
            'state',
            'origin',
            'destination',
            'geometry',
            'distance_meters',
            'duration_seconds',
            'planned_start',
            'planned_end',
            'calculated_at',
        )


class StopParticipantSerializer(serializers.ModelSerializer):
    passenger_name = serializers.CharField(source='participation.eligibility.passenger.user.name', read_only=True)
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = RouteStopParticipant
        fields = ('participation', 'operation', 'passenger_name', 'profile_picture_url')

    def get_profile_picture_url(self, obj) -> str | None:
        return user_avatar_url(obj.participation.eligibility.passenger.user, self.context.get('request'))


class StopSerializer(serializers.ModelSerializer):
    participants = StopParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = RouteStop
        fields = ('id', 'snapshot', 'position', 'point_snapshot', 'state', 'handled_at', 'participants')


class PublicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelPublication
        fields = ('id', 'travel', 'snapshot', 'revision', 'published_at')


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteOptimizationJob
        fields = ('id', 'snapshot', 'input_revision', 'status', 'attempts', 'error', 'created_at', 'updated_at')


class StopInput(InputSerializer):
    skipped = serializers.BooleanField(default=False)
