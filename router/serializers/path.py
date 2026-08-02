from rest_framework import serializers

from authenticator.models.company_route_group import CompanyRouteGroup
from router.models.path import Path


class PathSerializer(serializers.ModelSerializer):
    class Meta:
        model = Path
        fields = ['id', 'points', 'name', 'group']

    def validate_group(self, value):
        user = self.context['request'].user

        if not CompanyRouteGroup.objects.filter(id=value.id, company__user=user).exists():
            raise serializers.ValidationError('Este grupo de rotas não pertence à sua empresa.')

        return value
