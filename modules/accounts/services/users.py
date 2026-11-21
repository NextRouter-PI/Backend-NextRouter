"""Cadastro e atualização de conta de usuário com geocodificação fora da transação."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from modules.accounts.mixins.tokens import consume_email_token
from modules.accounts.models import EmailToken
from shared.geocoding import lookup_cep_brasilapi


def resolve_cep_coordinates(cep: str | None) -> tuple[float | None, float | None]:
    if not cep:
        return None, None
    cep_info = lookup_cep_brasilapi(cep)
    if cep_info and cep_info['latitude'] is not None and cep_info['longitude'] is not None:
        return cep_info['latitude'], cep_info['longitude']
    return None, None


def prepare_user_coords(validated_data: dict, *, instance=None) -> dict:
    """Resolve coordenadas via CEP antes de abrir qualquer transação de banco."""
    data = dict(validated_data)
    if instance is None:
        has_coords = data.get('latitude') is not None and data.get('longitude') is not None
        if has_coords:
            data['geocoded_at'] = timezone.now()
        else:
            data.pop('latitude', None)
            data.pop('longitude', None)
            lat, lon = resolve_cep_coordinates(data.get('cep'))
            if lat is not None and lon is not None:
                data['latitude'] = lat
                data['longitude'] = lon
                data['geocoded_at'] = timezone.now()
        return data

    new_cep = data.get('cep')
    missing_coords = instance.latitude is None or instance.longitude is None
    should_geocode = 'cep' in data and bool(new_cep) and (new_cep != instance.cep or missing_coords)
    if should_geocode:
        lat, lon = resolve_cep_coordinates(new_cep)
        if lat is not None and lon is not None:
            data['latitude'] = lat
            data['longitude'] = lon
            data['geocoded_at'] = timezone.now()
    return data


def create_user_account(validated_data: dict, *, token_instance: EmailToken, coords_prepared: bool = False):
    data = dict(validated_data) if coords_prepared else prepare_user_coords(validated_data)
    data.pop('code', None)
    pic_instance = data.pop('profile_picture', None)

    with transaction.atomic():
        consume_email_token(token_instance)
        if pic_instance:
            # A descrição da foto é exibida para outros usuários: não incluir o CPF.
            pic_instance.description = f'Foto de {data.get("name", "")}'
            pic_instance.save(update_fields=['description'])
        return get_user_model().objects.create_user(**data, profile_picture=pic_instance)


def update_user_account(instance, validated_data: dict, *, coords_prepared: bool = False):
    data = dict(validated_data) if coords_prepared else prepare_user_coords(validated_data, instance=instance)

    with transaction.atomic():
        old_pic_to_delete = None
        if 'profile_picture' in data:
            new_pic_instance = data.pop('profile_picture')
            old_pic_instance = instance.profile_picture
            if old_pic_instance and old_pic_instance != new_pic_instance:
                old_pic_to_delete = old_pic_instance
            if new_pic_instance:
                new_pic_instance.description = f'Foto de {data.get("name", instance.name)}'
                new_pic_instance.save(update_fields=['description'])
            instance.profile_picture = new_pic_instance

        for attr, value in data.items():
            setattr(instance, attr, value)

        instance.save()
        if old_pic_to_delete is not None:
            transaction.on_commit(old_pic_to_delete.delete)

    return instance
