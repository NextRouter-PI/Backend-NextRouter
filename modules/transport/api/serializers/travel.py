from rest_framework import serializers

from modules.transport.api.serializers.ownership import validate_driver_in_route_group, validate_route_group_ownership
from modules.transport.models.travel import Travel
from modules.transport.models.vehicle import Vehicle


class TravelListAndRetrieveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Travel
        fields = (
            'id',
            'company',
            'driver',
            'vehicle',
            'path',
            'status',
            'started_at',
            'finished_at',
            'current_latitude',
            'current_longitude',
            'location_updated_at',
        )
        read_only_fields = (
            'company',
            'driver',
            'vehicle',
            'path',
            'status',
            'started_at',
            'finished_at',
            'current_latitude',
            'current_longitude',
            'location_updated_at',
        )


class TravelCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Travel
        fields = (
            'id',
            'company',
            'driver',
            'vehicle',
            'path',
        )
        # A empresa da viagem é sempre a dona do trajeto (definida na view), nunca enviada pelo cliente.
        read_only_fields = ('company',)

    def validate_path(self, path):
        validate_route_group_ownership(self.context, path.route_group)
        return path

    def validate(self, attrs):
        path = attrs.get('path', getattr(self.instance, 'path', None))
        driver = attrs.get('driver', getattr(self.instance, 'driver', None))

        if path is not None:
            validate_driver_in_route_group(driver, path.route_group)
            if driver is None:
                raise serializers.ValidationError({'driver': 'Selecione um motorista para a viagem.'})

            if 'vehicle' not in attrs:
                vehicles = list(
                    Vehicle.objects.filter(route_group=path.route_group, driver=driver, status=Vehicle.Status.ACTIVE)[
                        :2
                    ]
                )
                if len(vehicles) != 1:
                    raise serializers.ValidationError({
                        'vehicle': 'Informe um veículo ativo do grupo para esta viagem.'
                    })
                attrs['vehicle'] = vehicles[0]

            vehicle = attrs['vehicle']
            if vehicle is None:
                raise serializers.ValidationError({'vehicle': 'Selecione um veículo para a viagem.'})
            if vehicle.route_group_id != path.route_group_id or vehicle.status != Vehicle.Status.ACTIVE:
                raise serializers.ValidationError({'vehicle': 'O veículo deve estar ativo neste grupo de rota.'})
            if vehicle.driver_id not in (None, driver.pk):
                raise serializers.ValidationError({'vehicle': 'O veículo está atribuído a outro motorista.'})
            if (
                vehicle.capacity is not None
                and path.route_group.passengers.filter(is_approved=True).count() > vehicle.capacity
            ):
                raise serializers.ValidationError({
                    'vehicle': 'A capacidade do veículo é menor que o grupo de passageiros.'
                })

        return attrs


class TravelLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    recorded_at = serializers.DateTimeField(required=False)
