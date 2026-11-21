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


class VehicleAssignmentInput(InputSerializer):
    vehicle_id = serializers.IntegerField(min_value=1)


class PositionSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    updated_at = serializers.DateTimeField()


class LocationSerializer(serializers.Serializer):
    position = PositionSerializer(allow_null=True)
    stale = serializers.BooleanField()
