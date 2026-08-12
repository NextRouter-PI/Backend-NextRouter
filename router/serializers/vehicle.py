from rest_framework import serializers

from authenticator.models.company_route_group import CompanyRouteGroup
from router.models.vehicle import Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            'id',
            'group',
            'garage_cep',
            'plate',
        )

    def validate_group(self, value):
        user = self.context['request'].user

        if not CompanyRouteGroup.objects.filter(id=value.id, company__user=user).exists():
            raise serializers.ValidationError('Este grupo de rotas não pertence à sua empresa.')

        return value
