from rest_framework import serializers

from modules.organizations.models import CompanyRouteGroup, OperationalPoint
from modules.transport.models import RecurringService, ResponsePolicy, Vehicle
from shared.api import InputModelSerializer, InputSerializer


class PointSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalPoint
        fields = (
            'id',
            'company',
            'name',
            'street',
            'number',
            'complement',
            'neighborhood',
            'city',
            'state',
            'cep',
            'latitude',
            'longitude',
        )


class PointInput(InputModelSerializer):
    class Meta:
        model = OperationalPoint
        fields = (
            'name',
            'street',
            'number',
            'complement',
            'neighborhood',
            'city',
            'state',
            'cep',
            'latitude',
            'longitude',
        )


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyRouteGroup
        fields = ('id', 'company', 'name', 'destination')


class GroupInput(InputSerializer):
    name = serializers.CharField(max_length=255)
    destination_id = serializers.IntegerField(min_value=1)


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponsePolicy
        fields = (
            'id',
            'route_group',
            'opens_days_before',
            'opens_time',
            'normal_days_before',
            'normal_time',
            'extension_days_before',
            'extension_time',
        )


class PolicyInput(InputModelSerializer):
    class Meta:
        model = ResponsePolicy
        fields = (
            'opens_days_before',
            'opens_time',
            'normal_days_before',
            'normal_time',
            'extension_days_before',
            'extension_time',
        )


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ('id', 'company', 'plate', 'model', 'year', 'capacity', 'status', 'garage_point', 'color', 'features')


class VehicleInput(InputModelSerializer):
    garage_point_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    class Meta:
        model = Vehicle
        fields = ('plate', 'model', 'year', 'capacity', 'status', 'garage_point_id', 'color', 'features')


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringService
        fields = (
            'id',
            'route_group',
            'name',
            'direction',
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
        )


class ServiceInput(InputModelSerializer):
    route_group_id = serializers.IntegerField(min_value=1)
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


class StopsInput(InputSerializer):
    point_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)


class GenerateInput(InputSerializer):
    start_date = serializers.DateField()
    horizon_days = serializers.IntegerField(min_value=1, max_value=31)
    batch_size = serializers.IntegerField(min_value=1, max_value=31)


class CancelDateInput(InputSerializer):
    date = serializers.DateField()
    reason = serializers.CharField(max_length=500)
