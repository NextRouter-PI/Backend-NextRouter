"""Helpers compartilhados pelos serializers da camada API de transporte."""


def user_avatar_url(user, request=None) -> str | None:
    """Resolve URL absoluta (quando há request) ou relativa da foto de perfil sem erros em arquivo ausente."""
    picture = getattr(user, 'profile_picture', None)
    if not picture or not picture.file:
        return None
    url = picture.file.url
    return request.build_absolute_uri(url) if request else url


def passenger_point_fields(group_membership, request=None) -> dict:
    """Monta projeção de endereço/ponto operacional do aluno com fallback para o endereço do usuário."""
    user = group_membership.membership.passenger.user
    point = group_membership.transport_point
    source = point if point is not None else user
    return {
        'group_membership_id': group_membership.pk,
        'passenger_name': user.name,
        'profile_picture_url': user_avatar_url(user, request),
        'cep': source.cep,
        'street': source.street,
        'number': source.number,
        'complement': source.complement,
        'neighborhood': source.neighborhood,
        'city': source.city,
        'state': source.state,
        'latitude': source.latitude,
        'longitude': source.longitude,
    }
