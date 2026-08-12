from rest_framework import serializers

from authenticator.models.company_route_group import CompanyRouteGroup
from router.models.company_route_schedule import CompanyRouteSchedule


class CompanyRouteScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyRouteSchedule
        fields = (
            'id',
            'route_group',
            'go_hour',
            'return_hour',
        )

    def validate_route_group(self, value):
        user = self.context['request'].user

        if not CompanyRouteGroup.objects.filter(id=value.id, company__user=user).exists():
            raise serializers.ValidationError('Este grupo de rota não pertence à sua empresa.')

        return value

    def validate(self, attrs):
        go_hour = attrs.get('go_hour')
        return_hour = attrs.get('return_hour')
        if self.instance:
            go_hour = go_hour or self.instance.go_hour
            return_hour = return_hour or self.instance.return_hour

        if go_hour and return_hour and return_hour <= go_hour:
            raise serializers.ValidationError({
                'return_hour': 'O horário de retorno deve ser posterior ao horário de ida.'
            })

        return attrs
