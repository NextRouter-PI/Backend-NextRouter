from rest_framework import serializers

from modules.transport.api.serializers.common import user_avatar_url
from modules.transport.models import (
    RouteOptimizationJob,
    RouteSnapshot,
    RouteStop,
    RouteStopParticipant,
    TravelPublication,
)
from modules.transport.services.eta import planned_at, stop_expectations
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
    planned_at = serializers.SerializerMethodField()
    expected_at = serializers.SerializerMethodField()
    delay_seconds = serializers.SerializerMethodField()

    class Meta:
        model = RouteStop
        fields = (
            'id',
            'snapshot',
            'position',
            'point_snapshot',
            'state',
            'handled_at',
            'participants',
            'planned_at',
            'expected_at',
            'delay_seconds',
        )

    def _eta(self, obj):
        # Uma conta por percurso na mesma resposta (a lista inteira compartilha o contexto).
        cache = self.context.setdefault('_eta', {})
        if obj.snapshot_id not in cache:
            cache[obj.snapshot_id] = stop_expectations(obj.snapshot)
        return cache[obj.snapshot_id]

    def get_planned_at(self, obj) -> str | None:
        value = planned_at(obj)
        return value.isoformat() if value else None

    def get_expected_at(self, obj) -> str | None:
        value = self._eta(obj)[0].get(obj.pk)
        return value.isoformat() if value else None

    def get_delay_seconds(self, obj) -> int:
        return self._eta(obj)[1]


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
