from rest_framework import serializers

from modules.transport.models import Travel
from shared.api import InputSerializer


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
        return bool(obj.is_published_current and obj.planning_status == Travel.PlanningStatus.READY)


class LiveTravelSerializer(serializers.Serializer):
    """Uma viagem em andamento no mapa geral da empresa."""

    id = serializers.IntegerField()
    direction = serializers.CharField()
    group_name = serializers.CharField(allow_blank=True)
    service_name = serializers.CharField(allow_blank=True)
    driver_name = serializers.CharField(allow_blank=True)
    vehicle_plate = serializers.CharField(allow_blank=True)
    started_at = serializers.DateTimeField(allow_null=True)
    planned_end = serializers.DateTimeField(allow_null=True)
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    location_updated_at = serializers.DateTimeField(allow_null=True)
    geometry = serializers.JSONField(allow_null=True)
    boarded = serializers.IntegerField()
    waiting = serializers.IntegerField()
    total = serializers.IntegerField()
    stops_done = serializers.IntegerField()
    stops_total = serializers.IntegerField()
    delay_seconds = serializers.IntegerField()
    next_stop_name = serializers.CharField(allow_blank=True)
    next_stop_expected_at = serializers.DateTimeField(allow_null=True)


class VehicleAssignmentInput(InputSerializer):
    vehicle_id = serializers.IntegerField(min_value=1)


class PositionSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    updated_at = serializers.DateTimeField()


class LocationSerializer(serializers.Serializer):
    position = PositionSerializer(allow_null=True)
    stale = serializers.BooleanField()
