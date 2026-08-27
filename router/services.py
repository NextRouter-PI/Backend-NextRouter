from app.geocoding import geocode_address
from router.models.path import Path


def ensure_route_group_geocoded(route_group):
    """
    Geocodifica o CEP em comum do grupo de rota, se ainda não tiver coordenadas.
    Usado para ter um ponto de referência central ao calcular rotas/paradas.
    """
    if route_group.reference_latitude is not None or not route_group.common_cep:
        return route_group

    latitude, longitude = geocode_address(cep=route_group.common_cep)
    if latitude is not None:
        from django.utils import timezone

        route_group.reference_latitude = latitude
        route_group.reference_longitude = longitude
        route_group.geocoded_at = timezone.now()
        route_group.save(update_fields=['reference_latitude', 'reference_longitude', 'geocoded_at'])

    return route_group


def ensure_default_path(route_group):
    """
    Garante que o grupo de rota tenha um trajeto (Path) para acumular as paradas
    dos passageiros/motoristas automaticamente.
    """
    path, _ = Path.objects.get_or_create(
        route_group=route_group,
        name='Trajeto automático',
        defaults={'points': []},
    )
    return path


def sync_stop_for_user(route_group, user, *, label=None):
    """
    Adiciona (ou atualiza) uma parada no trajeto automático do grupo de rota
    com a localização geocodificada do usuário. Não faz nada se o usuário
    ainda não tiver latitude/longitude (endereço incompleto ou não geocodificado).
    """
    if user.latitude is None or user.longitude is None:
        return None

    path = ensure_default_path(route_group)

    address_parts = [part for part in (user.street, user.number, user.neighborhood, user.city, user.state) if part]
    stop = {
        'user_id': user.id,
        'label': label or user.name,
        'latitude': user.latitude,
        'longitude': user.longitude,
        'address': ', '.join(address_parts),
    }

    points = [point for point in (path.points or []) if point.get('user_id') != user.id]
    points.append(stop)

    path.points = points
    path.save(update_fields=['points'])
    return path


def remove_stop_for_user(route_group, user):
    """Remove a parada do usuário do trajeto automático (ex.: ao trocar de grupo)."""
    path = Path.objects.filter(route_group=route_group, name='Trajeto automático').first()
    if not path:
        return None

    points = [point for point in (path.points or []) if point.get('user_id') != user.id]
    if len(points) != len(path.points or []):
        path.points = points
        path.save(update_fields=['points'])
    return path
