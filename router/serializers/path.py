from rest_framework import serializers

from authenticator.models.company_route_group import CompanyRouteGroup
from router.models.path import Path


class PathSerializer(serializers.ModelSerializer):
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
