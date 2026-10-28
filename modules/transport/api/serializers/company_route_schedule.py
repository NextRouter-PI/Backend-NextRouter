from django.db import transaction
from rest_framework import serializers

from modules.organizations.models.company_route_group import CompanyRouteGroup
from modules.transport.api.serializers.ownership import validate_route_group_ownership
from modules.transport.models.company_route_schedule import CompanyRouteSchedule


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

        route_group = attrs.get('route_group', getattr(self.instance, 'route_group', None))
        if route_group and go_hour and return_hour:
            overlapping = CompanyRouteSchedule.objects.filter(
                route_group=route_group, go_hour__lt=return_hour, return_hour__gt=go_hour
            )
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise serializers.ValidationError({'go_hour': 'Já existe um horário sobreposto neste grupo.'})

        return super().validate(attrs)

    @transaction.atomic
    def create(self, validated_data):
        CompanyRouteGroup.objects.select_for_update().get(pk=validated_data['route_group'].pk)
        self.validate(validated_data)
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        CompanyRouteGroup.objects.select_for_update().get(pk=validated_data.get('route_group', instance.route_group).pk)
        self.validate(validated_data)
        return super().update(instance, validated_data)


class CompanyRouteSchedulePatchSerializer(CompanyRouteScheduleCreateSerializer):
    pass
