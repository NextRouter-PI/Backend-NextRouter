from rest_framework import serializers


def validate_route_group_ownership(context, route_group):
    """
    Garante que o grupo de rota informado pertence à empresa autenticada,
    impedindo que uma empresa crie/edite registros nos grupos de outra empresa.
    """
    user = context['request'].user

    if not (user.is_staff or user.is_superuser) and route_group.company.user_id != user.id:
        raise serializers.ValidationError('Este grupo de rota não pertence à sua empresa.')

    return route_group


def validate_driver_in_route_group(driver, route_group, field_name='driver'):
    if driver is not None and driver.route_group_id != route_group.id:
        raise serializers.ValidationError({field_name: 'O motorista não pertence a este grupo de rota.'})
    if driver is not None and not driver.is_approved:
        raise serializers.ValidationError({field_name: 'O motorista ainda não foi aprovado para este grupo.'})
