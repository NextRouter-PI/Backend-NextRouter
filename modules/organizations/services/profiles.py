"""Serviços transacionais de cadastro e atualização de perfis organizacionais."""

from django.db import transaction
from django.utils import timezone

from modules.accounts.services import (
    create_user_account,
    prepare_user_coords,
    resolve_cep_coordinates,
    update_user_account,
)
from modules.organizations.models import Company

COMPANY_DOCUMENT_FIELDS = (
    'articles_of_association_document',
    'state_operating_license_document',
    'certificate_of_good_stading_document',
)


def create_company_profile(validated_data: dict, *, token_instance) -> Company:
    data = dict(validated_data)
    # Consultas CEP externas (usuário e empresa) sempre fora da transação de banco.
    user_data = prepare_user_coords(data.pop('user'))

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

    with transaction.atomic():
        user = create_user_account(user_data, token_instance=token_instance, coords_prepared=True)
        return Company.objects.create(user=user, **data)


def update_company_profile(instance: Company, validated_data: dict) -> Company:
    data = dict(validated_data)
    raw_user_data = data.pop('user', None)
    user_data = prepare_user_coords(raw_user_data, instance=instance.user) if raw_user_data else None

    with transaction.atomic():
        if user_data:
            update_user_account(instance.user, user_data, coords_prepared=True)

        docs_to_delete = []
        for doc_field in COMPANY_DOCUMENT_FIELDS:
            if doc_field in data:
                new_doc = data.pop(doc_field)
                old_doc = getattr(instance, doc_field, None)
                if old_doc and old_doc != new_doc:
                    docs_to_delete.append(old_doc)
                setattr(instance, doc_field, new_doc)

        for attr, value in data.items():
            setattr(instance, attr, value)
        instance.save()

        retained_ids = {getattr(instance, f'{field}_id', None) for field in COMPANY_DOCUMENT_FIELDS}
        for old_doc in docs_to_delete:
            if old_doc.pk not in retained_ids:
                transaction.on_commit(old_doc.delete)

    return instance
