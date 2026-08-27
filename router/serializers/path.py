from rest_framework import serializers

from router.models.path import Path


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


class PathPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Path
        fields = (
            'id',
            'points',
            'name',
            'route_group',
        )
