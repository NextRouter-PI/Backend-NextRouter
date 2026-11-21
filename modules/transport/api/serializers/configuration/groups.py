from rest_framework import serializers

from modules.organizations.models import CompanyRouteGroup
from modules.transport.models import AutomationSchedule, ResponsePolicy
from shared.api import InputModelSerializer, InputSerializer

POLICY_FIELDS = (
    'opens_days_before',
    'opens_time',
    'normal_days_before',
    'normal_time',
    'extension_days_before',
    'extension_time',
)


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyRouteGroup
        fields = ('id', 'company', 'name', 'destination')


class GroupInput(InputSerializer):
    name = serializers.CharField(max_length=255)
    destination_id = serializers.IntegerField(min_value=1)


class GroupUpdateInput(GroupInput):
    def to_service_kwargs(self, group) -> dict:
        return {
            'name': self.validated_data.get('name', group.name),
            'destination_id': self.validated_data.get('destination_id', group.destination_id),
        }


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponsePolicy
        fields = ('id', 'route_group', *POLICY_FIELDS)


class PolicyInput(InputModelSerializer):
    class Meta:
        model = ResponsePolicy
        fields = POLICY_FIELDS


class _HorizonBatchValidationMixin(InputSerializer):
    horizon_days = serializers.IntegerField(min_value=1, max_value=31)
    batch_size = serializers.IntegerField(min_value=1, max_value=31)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs['batch_size'] > attrs['horizon_days']:
            raise serializers.ValidationError({'batch_size': 'O tamanho do lote não pode exceder o horizonte.'})
        return attrs


class GenerateInput(_HorizonBatchValidationMixin):
    start_date = serializers.DateField()
    excluded_dates = serializers.ListField(child=serializers.DateField(), required=False, default=list)


class CancelDateInput(InputSerializer):
    date = serializers.DateField()
    reason = serializers.CharField(max_length=500)


class AutomationInput(_HorizonBatchValidationMixin):
    enabled = serializers.BooleanField()
    interval_seconds = serializers.IntegerField(min_value=1, max_value=2147483647)
    next_run_at = serializers.DateTimeField()
    expected_revision = serializers.IntegerField(min_value=0)


class AutomationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationSchedule
        fields = (
            'id',
            'route_group',
            'enabled',
            'horizon_days',
            'batch_size',
            'interval_seconds',
            'next_run_at',
            'cursor_date',
            'cycle_end_date',
            'last_attempted_at',
            'last_completed_at',
            'last_error_code',
            'revision',
            'configured_at',
        )
