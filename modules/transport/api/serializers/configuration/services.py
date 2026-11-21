from rest_framework import serializers

from modules.transport.models import RecurringService
from shared.api import InputModelSerializer, InputSerializer


class ServiceSerializer(serializers.ModelSerializer):
    point_ids = serializers.SerializerMethodField()

    class Meta:
        model = RecurringService
        fields = (
            'id',
            'route_group',
            'name',
            'direction',
            'is_shared',
            'weekdays',
            'target_time',
            'valid_from',
            'valid_until',
            'driver_membership',
            'vehicle',
            'origin',
            'destination',
            'planned_duration',
            'turnaround_duration',
            'point_ids',
        )

    def get_point_ids(self, obj) -> list[int]:
        return [stop.point_id for stop in obj.configured_stops.all()]


class ServiceInput(InputModelSerializer):
    route_group_id = serializers.IntegerField(min_value=1)
    is_shared = serializers.BooleanField(required=False, default=False)
    weekdays = serializers.IntegerField(
        min_value=1, max_value=127, help_text='Máscara: segunda=1, terça=2, ... domingo=64.'
    )
    valid_from = serializers.DateField(required=False, allow_null=True)
    valid_until = serializers.DateField(required=False, allow_null=True)
    driver_membership_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    vehicle_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    origin_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    destination_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    class Meta:
        model = RecurringService
        fields = (
            'route_group_id',
            'name',
            'direction',
            'is_shared',
            'weekdays',
            'target_time',
            'valid_from',
            'valid_until',
            'driver_membership_id',
            'vehicle_id',
            'origin_id',
            'destination_id',
            'planned_duration',
            'turnaround_duration',
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        valid_from = attrs.get('valid_from')
        valid_until = attrs.get('valid_until')
        if valid_from and valid_until and valid_until < valid_from:
            raise serializers.ValidationError({'valid_until': 'A data final não pode ser anterior à data inicial.'})
        return attrs


class ServiceUpdateInput(ServiceInput):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        service = self.context.get('service')
        if service is not None:
            if attrs.pop('route_group_id', service.route_group_id) != service.route_group_id:
                raise serializers.ValidationError({'route_group_id': 'O grupo do serviço não pode ser alterado.'})
            valid_from = attrs.get('valid_from', service.valid_from)
            valid_until = attrs.get('valid_until', service.valid_until)
            if valid_from and valid_until and valid_until < valid_from:
                raise serializers.ValidationError({'valid_until': 'A data final não pode ser anterior à data inicial.'})
        return attrs


class StopsInput(InputSerializer):
    point_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)
