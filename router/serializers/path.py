from rest_framework import serializers

from router.models.path import Path
from router.serializers.ownership import validate_route_group_ownership


class PathListAndRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Path
        fields = (
            'id',
            'points',
            'name',
            'route_group',
        )


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
    pass
