from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from modules.transport.models import (
    DailyChangeRequest,
    DailyResponse,
    RecurringService,
    ServiceDay,
    ServiceDayEligibility,
)
from shared.api import InputSerializer


class DaySerializer(serializers.ModelSerializer):
    window = serializers.SerializerMethodField()
    issues = serializers.SerializerMethodField()

    class Meta:
        model = ServiceDay
        fields = (
            'id',
            'route_group',
            'date',
            'opens_at',
            'normal_deadline',
            'extension_deadline',
            'revision',
            'canceled_at',
            'window',
            'issues',
        )

    def get_window(self, obj) -> str:
        now = timezone.now()
        if obj.canceled_at:
            return 'canceled'
        if now < obj.opens_at:
            return 'not_open'
        if now < obj.normal_deadline:
            return 'normal'
        if obj.extension_deadline and now < obj.extension_deadline:
            return 'extension'
        return 'closed'

    def get_issues(self, obj) -> list[str]:
        if obj.route_group.company.user_id != self.context['request'].user.pk:
            return []
        data = obj.configuration_snapshot
        return [*data.get('issues', []), *([data['operational_issue']] if data.get('operational_issue') else [])]


class CancelDaySerializer(serializers.Serializer):
    day = DaySerializer()
    partial = serializers.BooleanField()
    preserved_travel_ids = serializers.ListField(child=serializers.IntegerField())


class ResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyResponse
        fields = (
            'id',
            'eligibility',
            'outbound_service',
            'return_service',
            'answered_at',
            'revision',
            'outbound_withdrawn_at',
            'return_withdrawn_at',
        )


class AuthorizedServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringService
        fields = ('id', 'name', 'direction', 'is_shared', 'target_time')


class EligibilitySerializer(serializers.ModelSerializer):
    response = ResponseSerializer(read_only=True, allow_null=True)
    authorized_services = serializers.SerializerMethodField()

    class Meta:
        model = ServiceDayEligibility
        fields = (
            'id',
            'day',
            'passenger',
            'authorized_service_ids',
            'authorized_services',
            'point_snapshot',
            'response',
        )

    @extend_schema_field(AuthorizedServiceSerializer(many=True))
    def get_authorized_services(self, obj):
        services = RecurringService.objects.filter(
            pk__in=obj.authorized_service_ids, route_group_id=obj.day.route_group_id
        )
        return AuthorizedServiceSerializer(services.order_by('pk'), many=True).data


class AnswerInput(InputSerializer):
    outbound_service_id = serializers.IntegerField(min_value=1, allow_null=True)
    return_service_id = serializers.IntegerField(min_value=1, allow_null=True)
    expected_revision = serializers.IntegerField(min_value=0)


class LegInput(InputSerializer):
    leg = serializers.ChoiceField(choices=RecurringService.Direction.choices)


class ChangeInput(LegInput):
    proposed_service_id = serializers.IntegerField(min_value=1)
    expected_revision = serializers.IntegerField(min_value=0)


class ChangeRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyChangeRequest
        fields = (
            'id',
            'response',
            'leg',
            'proposed_service',
            'expected_response_revision',
            'created_at',
            'expires_at',
            'status',
            'decided_at',
            'application',
            'applied_at',
            'closed_at',
            'reason',
        )


class CancelInput(InputSerializer):
    reason = serializers.CharField(max_length=500)
