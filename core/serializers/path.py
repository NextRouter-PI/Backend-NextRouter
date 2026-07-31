from rest_framework import serializers

from core.models.company_route_group import CompanyRouteGroup
from core.models.path import Path


class PathSerializer(serializers.ModelSerializer):
    class Meta:
        model = Path
        fields = ['points', 'name', 'group_id']

    def validate_group_id(self, value):
        user = self.context['request'].user
        if not CompanyRouteGroup.objects.filter(id=value.id, company__user=user).exists():
            raise serializers.ValidationError('Este grupo não pertence à sua empresa.')
        return value
