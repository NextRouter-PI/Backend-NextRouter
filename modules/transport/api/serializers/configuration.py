from rest_framework import serializers

from modules.organizations.models import CompanyRouteGroup, HabitualRoute, OperationalPoint
from modules.transport.models import AutomationSchedule, RecurringService, ResponsePolicy, Vehicle
from shared.api import InputModelSerializer, InputSerializer


class PointSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalPoint
        fields = (
            'id',
            'company',
            'point_type',
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
            'point_type',
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


class StopsInput(InputSerializer):
    point_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)


class GenerateInput(InputSerializer):
    start_date = serializers.DateField()
    horizon_days = serializers.IntegerField(min_value=1, max_value=31)
    batch_size = serializers.IntegerField(min_value=1, max_value=31)
    excluded_dates = serializers.ListField(child=serializers.DateField(), required=False, default=list)


class CancelDateInput(InputSerializer):
    date = serializers.DateField()
    reason = serializers.CharField(max_length=500)


class AutomationInput(InputSerializer):
    enabled = serializers.BooleanField()
    horizon_days = serializers.IntegerField(min_value=1, max_value=31)
    batch_size = serializers.IntegerField(min_value=1, max_value=31)
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


class RoutePassengerPointInput(InputSerializer):
    group_membership_id = serializers.IntegerField(min_value=1)
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)


class HabitualRouteInput(InputSerializer):
    route_group_id = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=100)
    kind = serializers.ChoiceField(choices=HabitualRoute.Kind.choices, default=HabitualRoute.Kind.HABITUAL)
    passengers = RoutePassengerPointInput(many=True, required=False)


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

    def _is_company_owner(self, obj):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and obj.route_group.company.user_id == user.pk)

    def get_destination_name(self, obj) -> str:
        dest = obj.route_group.destination
        return f'{dest.name} ({dest.city}/{dest.state})' if dest else ''

    def get_services(self, obj) -> list[dict]:
        return [
            {
                'id': srv.pk,
                'name': srv.name,
                'direction': srv.direction,
                'is_shared': srv.is_shared,
                'target_time': str(srv.target_time)[:5],
                'weekdays': srv.weekdays,
            }
            for srv in obj.route_group.services.all().order_by('direction', 'target_time', 'pk')
        ]

    def get_passengers(self, obj) -> list[dict]:
        # Privacidade: somente a empresa dona visualiza a lista e os pontos dos passageiros da rota.
        if not self._is_company_owner(obj):
            return []
        result = []
        for gm in obj.passenger_memberships.filter(ended_at__isnull=True, membership__status='active').select_related(
            'membership__passenger__user', 'transport_point'
        ):
            user = gm.membership.passenger.user
            point = gm.transport_point
            result.append({
                'group_membership_id': gm.pk,
                'passenger_name': user.name,
                'street': point.street if point else user.street,
                'number': point.number if point else user.number,
                'complement': point.complement if point else user.complement,
                'neighborhood': point.neighborhood if point else user.neighborhood,
                'city': point.city if point else user.city,
                'state': point.state if point else user.state,
                'cep': point.cep if point else user.cep,
                'latitude': point.latitude if point else user.latitude,
                'longitude': point.longitude if point else user.longitude,
            })
        return result

    def get_my_point(self, obj) -> dict | None:
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated or self._is_company_owner(obj):
            return None
        gm = (
            obj.passenger_memberships.filter(
                ended_at__isnull=True,
                membership__status='active',
                membership__passenger__user=user,
            )
            .select_related('transport_point')
            .first()
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
    cep = serializers.CharField(allow_blank=True)
    street = serializers.CharField(allow_blank=True)
    number = serializers.CharField(allow_blank=True)
    complement = serializers.CharField(allow_blank=True)
    neighborhood = serializers.CharField(allow_blank=True)
    city = serializers.CharField(allow_blank=True)
    state = serializers.CharField(allow_blank=True)
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
