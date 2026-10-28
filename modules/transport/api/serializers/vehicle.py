from django.utils import timezone
from rest_framework import serializers

from modules.transport.api.serializers.ownership import validate_driver_in_route_group, validate_route_group_ownership
from modules.transport.models.vehicle import Vehicle


class VehicleListAndRetrieveSerializer(serializers.ModelSerializer):
    driver_name = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = (
            'id',
            'route_group',
            'garage_cep',
            'plate',
            'model',
            'year',
            'capacity',
            'status',
            'color',
            'features',
            'driver',
            'driver_name',
        )

    def get_driver_name(self, obj) -> str | None:
        return obj.driver.user.name.title() if obj.driver else None


class VehicleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = (
            'id',
            'route_group',
            'garage_cep',
            'plate',
            'model',
            'year',
            'capacity',
            'status',
            'color',
            'features',
            'driver',
        )

    def validate_route_group(self, route_group):
        return validate_route_group_ownership(self.context, route_group)

    def validate_plate(self, plate):
        plate = plate.replace('-', '').replace(' ', '').upper()
        queryset = Vehicle.objects.filter(plate=plate)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('Já existe um veículo cadastrado com esta placa.')
        return plate

    def validate_capacity(self, capacity):
        if capacity is not None and capacity < 1:
            raise serializers.ValidationError('A capacidade do veículo deve ser de pelo menos 1 passageiro.')
        return capacity

    def validate_year(self, year):
        if year is not None and not (1950 <= year <= timezone.now().year + 1):
            raise serializers.ValidationError('Informe um ano válido para o veículo.')
        return year

    def validate(self, attrs):
        route_group = attrs.get('route_group', getattr(self.instance, 'route_group', None))
        driver = attrs.get('driver', getattr(self.instance, 'driver', None))

        if route_group is not None:
            validate_driver_in_route_group(driver, route_group)

        return attrs


class VehiclePatchSerializer(VehicleCreateSerializer):
    pass
