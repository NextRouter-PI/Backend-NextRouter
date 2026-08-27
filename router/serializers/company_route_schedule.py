from rest_framework import serializers

from router.models.company_route_schedule import CompanyRouteSchedule


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

    def validate(self, attrs):
        go_hour = attrs.get('go_hour')
        return_hour = attrs.get('return_hour')

        if go_hour and return_hour and return_hour <= go_hour:
            raise serializers.ValidationError({
                'return_hour': 'O horário de retorno deve ser posterior ao horário de ida.'
            })

        return attrs


class CompanyRouteSchedulePatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyRouteSchedule
        fields = (
            'id',
            'route_group',
            'go_hour',
            'return_hour',
        )
