from rest_framework import serializers

from modules.transport.api.serializers.common import user_avatar_url
from modules.transport.models import ParticipationEvent, TravelParticipation
from modules.transport.services.eta import participation_timing
from shared.api import OperationInput


class ParticipantSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='eligibility.passenger.user.name', read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    point_snapshot = serializers.JSONField(source='eligibility.point_snapshot', read_only=True)
    # Previsão da parada deste passageiro: horário previsto/esperado e paradas antes dele.
    timing = serializers.SerializerMethodField()

    class Meta:
        model = TravelParticipation
        fields = (
            'id',
            'travel',
            'eligibility',
            'leg',
            'name',
            'profile_picture_url',
            'point_snapshot',
            'status',
            'allocated_at',
            'withdrawn_at',
            'no_show_at',
            'boarded_at',
            'dropped_off_at',
            'timing',
        )

    def get_timing(self, obj) -> dict | None:
        if obj.status not in ('allocated', 'on_board') or obj.travel.status in ('finished', 'canceled'):
            return None
        return participation_timing(obj)

    def get_profile_picture_url(self, obj) -> str | None:
        return user_avatar_url(obj.eligibility.passenger.user, self.context.get('request'))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        is_operational = bool(
            user
            and user.is_authenticated
            and (
                user.pk == instance.travel.company.user_id
                or user.pk == getattr(instance.travel.driver, 'user_id', None)
            )
        )
        if not is_operational:
            data.pop('point_snapshot', None)
        return data


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParticipationEvent
        fields = ('id', 'participation', 'kind', 'actor', 'occurred_at', 'operation_id', 'corrects', 'reason')


class PresenceInput(OperationInput):
    kind = serializers.ChoiceField(
        choices=[
            ParticipationEvent.Kind.BOARDED,
            ParticipationEvent.Kind.NO_SHOW,
            ParticipationEvent.Kind.DROPPED_OFF,
        ]
    )


class CorrectionInput(OperationInput):
    corrects_event_id = serializers.IntegerField(min_value=1)
    target_status = serializers.ChoiceField(choices=TravelParticipation.Status.values)
    reason = serializers.CharField(max_length=500)


class PassengerRouteSerializer(serializers.Serializer):
    to_me = serializers.JSONField(allow_null=True)
    to_destination = serializers.JSONField(allow_null=True)
