from rest_framework import serializers

from router.models.company_route_schedule import CompanyRouteSchedule
from router.serializers.ownership import validate_route_group_ownership


class CompanyRouteScheduleListAndRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyRouteSchedule
        fields = (
            'id',
            'route_group',
            'go_hour',
            'return_hour',
        )


class CompanyRouteScheduleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyRouteSchedule
        fields = (
            'id',
            'route_group',
            'go_hour',
            'return_hour',
        )

    def validate_route_group(self, route_group):
        return validate_route_group_ownership(self.context, route_group)

    def validate(self, attrs):
        # Em um PATCH parcial, compara com os valores atuais que não foram enviados.
        go_hour = attrs.get('go_hour', getattr(self.instance, 'go_hour', None))
        return_hour = attrs.get('return_hour', getattr(self.instance, 'return_hour', None))

        if go_hour and return_hour and return_hour <= go_hour:
            raise serializers.ValidationError({
                'return_hour': 'O horário de retorno deve ser posterior ao horário de ida.'
            })

        return super().validate(attrs)


class CompanyRouteSchedulePatchSerializer(CompanyRouteScheduleCreateSerializer):
    pass
