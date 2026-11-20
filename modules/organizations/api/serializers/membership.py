from rest_framework import serializers

from modules.organizations.models import CompanyMembership, MembershipEvent, PassengerGroupMembership
from shared.api import InputSerializer


class MembershipSerializer(serializers.ModelSerializer):
    applicant_name = serializers.SerializerMethodField()
    requested_route_group_name = serializers.CharField(
        source='requested_route_group.name', read_only=True, default=None
    )

    class Meta:
        model = CompanyMembership
        fields = (
            'id',
            'applicant_name',
            'company',
            'passenger',
            'driver',
            'requested_route_group',
            'requested_route_group_name',
            'status',
            'created_at',
            'reviewed_at',
            'withdrawn_at',
            'ended_at',
        )

    def get_applicant_name(self, obj) -> str:
        return (obj.passenger or obj.driver).user.name


class MembershipInput(InputSerializer):
    company_id = serializers.IntegerField(min_value=1)
    profile = serializers.ChoiceField(choices=['passenger', 'driver'])
    route_group_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)


class MembershipEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipEvent
        fields = ('id', 'membership', 'action', 'actor', 'occurred_at', 'reason')


class GroupMembershipSerializer(serializers.ModelSerializer):
    service_ids = serializers.SerializerMethodField()
    habitual_outbound_id = serializers.SerializerMethodField()

    class Meta:
        model = PassengerGroupMembership
        fields = (
            'id',
            'membership',
            'route_group',
            'transport_point',
            'started_at',
            'ended_at',
            'service_ids',
            'habitual_outbound_id',
        )

    def get_service_ids(self, obj) -> list[int]:
        return [authorization.service_id for authorization in obj.service_authorizations.all()]

    def get_habitual_outbound_id(self, obj) -> int | None:
        return next(
            (
                authorization.service_id
                for authorization in obj.service_authorizations.all()
                if authorization.is_habitual
            ),
            None,
        )


class AssignGroupInput(InputSerializer):
    route_group_id = serializers.IntegerField(min_value=1)
    transport_point_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)


class AuthorizationsInput(InputSerializer):
    service_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)
    habitual_outbound_id = serializers.IntegerField(min_value=1, allow_null=True, default=None)
