from rest_framework import serializers

from modules.transport.models import (
    DriverInvitation,
    Notification,
    ParticipationEvent,
    RouteOptimizationJob,
    RouteSnapshot,
    RouteStop,
    RouteStopParticipant,
    Travel,
    TravelParticipation,
    TravelPublication,
)
from shared.api import InputSerializer, OperationInput


class TravelSerializer(serializers.ModelSerializer):
    date = serializers.DateField(source='service_day.date', read_only=True)
    direction = serializers.CharField(source='service.direction', read_only=True)
    publication_current = serializers.SerializerMethodField()

    class Meta:
        model = Travel
        fields = (
            'id',
            'company',
            'service_day',
            'service',
            'date',
            'direction',
            'driver',
            'vehicle',
            'planned_start',
            'planned_end',
            'status',
            'planning_status',
            'revision',
            'published_revision',
            'publication_current',
            'current_snapshot',
            'published_snapshot',
            'started_at',
            'finished_at',
        )

    def get_publication_current(self, obj) -> bool:
        return bool(
            obj.published_revision == obj.revision
            and obj.current_snapshot_id
            and obj.published_snapshot_id == obj.current_snapshot_id
            and obj.planning_status == 'ready'
        )


class ParticipantSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='eligibility.passenger.user.name', read_only=True)

    class Meta:
        model = TravelParticipation
        fields = (
            'id',
            'travel',
            'eligibility',
            'leg',
            'name',
            'status',
            'allocated_at',
            'withdrawn_at',
            'no_show_at',
            'boarded_at',
            'dropped_off_at',
        )


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParticipationEvent
        fields = ('id', 'participation', 'kind', 'actor', 'occurred_at', 'operation_id', 'corrects', 'reason')


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
    class Meta:
        model = RouteStopParticipant
        fields = ('participation', 'operation')


class StopSerializer(serializers.ModelSerializer):
    participants = StopParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = RouteStop
        fields = ('id', 'snapshot', 'position', 'point_snapshot', 'state', 'handled_at', 'participants')


class PublicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelPublication
        fields = ('id', 'travel', 'snapshot', 'revision', 'published_at')


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


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'kind', 'resource_type', 'resource_id', 'payload', 'created_at', 'read_at')


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteOptimizationJob
        fields = ('id', 'snapshot', 'input_revision', 'status', 'attempts', 'error', 'created_at', 'updated_at')


class InviteInput(InputSerializer):
    driver_membership_id = serializers.IntegerField(min_value=1)
    expires_at = serializers.DateTimeField()


class InviteResponseInput(InputSerializer):
    accept = serializers.BooleanField()


class VehicleAssignmentInput(InputSerializer):
    vehicle_id = serializers.IntegerField(min_value=1)


class PresenceInput(OperationInput):
    kind = serializers.ChoiceField(choices=['boarded', 'no_show', 'dropped_off'])


class CorrectionInput(OperationInput):
    corrects_event_id = serializers.IntegerField(min_value=1)
    target_status = serializers.ChoiceField(choices=['allocated', 'on_board', 'dropped_off', 'no_show', 'withdrawn'])
    reason = serializers.CharField(max_length=500)


class StopInput(InputSerializer):
    skipped = serializers.BooleanField(default=False)


class PositionSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    updated_at = serializers.DateTimeField()


class LocationSerializer(serializers.Serializer):
    position = PositionSerializer(allow_null=True)
    stale = serializers.BooleanField()
