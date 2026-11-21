from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from modules.organizations.models import HabitualRoute
from modules.transport.api.serializers.common import passenger_point_fields
from shared.api import InputSerializer


class RoutePassengerPointInput(InputSerializer):
    group_membership_id = serializers.IntegerField(min_value=1)
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class HabitualRouteInput(InputSerializer):
    route_group_id = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=100)
    kind = serializers.ChoiceField(choices=HabitualRoute.Kind.choices, default=HabitualRoute.Kind.HABITUAL)
    passengers = RoutePassengerPointInput(many=True, required=False)


class HabitualRouteUpdateInput(HabitualRouteInput):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs.pop('route_group_id', None)
        return attrs

    def to_service_kwargs(self, route) -> dict:
        return {
            'name': self.validated_data.get('name', route.name),
            'kind': self.validated_data.get('kind', route.kind),
            'passengers': self.validated_data.get('passengers'),
        }


class HabitualRouteSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='route_group.name', read_only=True)
    destination_name = serializers.SerializerMethodField()
    passengers = serializers.SerializerMethodField()
    my_point = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()

    class Meta:
        model = HabitualRoute
        fields = (
            'id',
            'route_group',
            'group_name',
            'destination_name',
            'name',
            'kind',
            'created_at',
            'passengers',
            'my_point',
            'services',
        )

    def _is_company_owner(self, obj) -> bool:
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and obj.route_group.company.user_id == user.pk)

    def _active_members(self, obj):
        prefetched = getattr(obj, 'active_route_members', None)
        if prefetched is not None:
            return prefetched
        return list(
            obj.passenger_memberships.active_members().select_related(
                'membership__passenger__user',
                'membership__passenger__user__profile_picture',
                'transport_point',
            )
        )

    def get_destination_name(self, obj) -> str:
        dest = obj.route_group.destination
        return f'{dest.name} ({dest.city}/{dest.state})' if dest else ''

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_services(self, obj) -> list[dict]:
        services = getattr(obj.route_group, 'ordered_services', None)
        if services is None:
            services = obj.route_group.services.all().order_by('direction', 'target_time', 'pk')
        return [
            {
                'id': srv.pk,
                'name': srv.name,
                'direction': srv.direction,
                'is_shared': srv.is_shared,
                'target_time': str(srv.target_time)[:5],
                'weekdays': srv.weekdays,
            }
            for srv in services
        ]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_passengers(self, obj) -> list[dict]:
        # Privacidade: somente a empresa dona visualiza a lista e os pontos dos passageiros da rota.
        if not self._is_company_owner(obj):
            return []
        request = self.context.get('request')
        return [passenger_point_fields(gm, request) for gm in self._active_members(obj)]

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_my_point(self, obj) -> dict | None:
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or self._is_company_owner(obj):
            return None
        gm = next(
            (member for member in self._active_members(obj) if member.membership.passenger.user_id == user.pk),
            None,
        )
        if not gm or not gm.transport_point:
            return None
        p = gm.transport_point
        return {
            'name': p.name,
            'street': p.street,
            'number': p.number,
            'complement': p.complement,
            'neighborhood': p.neighborhood,
            'city': p.city,
            'state': p.state,
            'latitude': p.latitude,
            'longitude': p.longitude,
        }


class UnassignedPassengerSerializer(serializers.Serializer):
    group_membership_id = serializers.IntegerField()
    membership_id = serializers.IntegerField()
    passenger_name = serializers.CharField()
    profile_picture_url = serializers.CharField(allow_null=True, required=False)
    cep = serializers.CharField(allow_blank=True)
    street = serializers.CharField(allow_blank=True)
    number = serializers.CharField(allow_blank=True)
    complement = serializers.CharField(allow_blank=True)
    neighborhood = serializers.CharField(allow_blank=True)
    city = serializers.CharField(allow_blank=True)
    state = serializers.CharField(allow_blank=True)
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)

    @classmethod
    def from_group_membership(cls, gm, request=None) -> dict:
        return {'membership_id': gm.membership_id, **passenger_point_fields(gm, request)}
