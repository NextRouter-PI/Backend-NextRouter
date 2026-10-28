from django.conf import settings
from rest_framework import serializers

from modules.transport.api.serializers.ownership import validate_route_group_ownership
from modules.transport.models.path import Path


class PathListAndRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Path
        fields = (
            'id',
            'points',
            'name',
            'route_group',
            'start_point',
            'end_point',
            'distance_meters',
            'duration_seconds',
            'geometry',
            'is_outdated',
            'optimized_at',
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        is_owner_or_admin = bool(
            user
            and (
                user.is_staff
                or user.is_superuser
                or (instance.route_group.company.is_approved and instance.route_group.company.user_id == user.pk)
            )
        )
        if not is_owner_or_admin:
            data['points'] = [
                {key: stop[key] for key in ('latitude', 'longitude') if key in stop} for stop in data['points']
            ]
        return data


class OptimizedPathResponseSerializer(PathListAndRetrieveSerializer):
    job_id = serializers.IntegerField()
    status = serializers.CharField()
    order = serializers.ListField(child=serializers.IntegerField(), required=False)

    class Meta(PathListAndRetrieveSerializer.Meta):
        fields = (*PathListAndRetrieveSerializer.Meta.fields, 'job_id', 'status', 'order')


class PathCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Path
        fields = (
            'id',
            'points',
            'name',
            'route_group',
        )

    def validate_route_group(self, route_group):
        return validate_route_group_ownership(self.context, route_group)

    def validate_points(self, points):
        if not isinstance(points, list):
            raise serializers.ValidationError('Os pontos de parada devem ser uma lista.')
        return points


class PathPatchSerializer(PathCreateSerializer):
    def update(self, instance, validated_data):
        if any(field in validated_data for field in ('points', 'route_group')):
            validated_data['is_outdated'] = True
        return super().update(instance, validated_data)


class WaypointSerializer(serializers.Serializer):
    latitude = serializers.FloatField(required=False, min_value=-90, max_value=90)
    longitude = serializers.FloatField(required=False, min_value=-180, max_value=180)
    street = serializers.CharField(required=False)
    number = serializers.CharField(required=False)
    neighborhood = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    state = serializers.CharField(required=False)
    cep = serializers.CharField(required=False)
    label = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if ('latitude' in attrs) != ('longitude' in attrs):
            raise serializers.ValidationError('Informe latitude e longitude juntas.')
        if 'latitude' not in attrs and not all(attrs.get(field) for field in ('street', 'number', 'city', 'cep')):
            raise serializers.ValidationError('Informe coordenadas ou endereço completo.')
        return attrs


class OptimizePathSerializer(serializers.Serializer):
    passenger_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=settings.OSRM_MAX_STOPS,
        required=False,
        default=list,
    )
    stops = serializers.ListField(
        child=WaypointSerializer(),
        min_length=1,
        max_length=settings.OSRM_MAX_STOPS,
        required=False,
        default=list,
    )
    start = WaypointSerializer()
    end = WaypointSerializer(required=False, allow_null=True, default=None)
    async_mode = serializers.BooleanField(required=False, default=False)

    def validate_passenger_ids(self, ids):
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Não repita passageiros na mesma rota.')
        return ids

    def validate(self, attrs):
        total_stops = len(attrs.get('passenger_ids') or []) + len(attrs.get('stops') or [])
        if total_stops < 1:
            raise serializers.ValidationError('Informe ao menos uma parada (passenger_ids ou stops).')
        if total_stops > settings.OSRM_MAX_STOPS:
            raise serializers.ValidationError(f'O limite máximo é de {settings.OSRM_MAX_STOPS} paradas por rota.')
        return attrs
