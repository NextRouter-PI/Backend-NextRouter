from django.db import transaction
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from modules.accounts.api.serializers.user import UserCreateSerializer, UserPatchSerializer
from modules.accounts.services import create_user_account, prepare_user_coords, update_user_account


class BaseProfileCreateSerializer(serializers.ModelSerializer):
    user_data = UserCreateSerializer(source='user')

    def create_profile_for_user(self, model_class, validated_data):
        # `user_data` já foi validado pelo serializer aninhado (inclusive o código do e-mail em
        # context['token_instance']). Resolve CEP antes da transação para não segurar conexão/locks.
        data = dict(validated_data)
        user_data = prepare_user_coords(data.pop('user'))
        with transaction.atomic():
            user = create_user_account(
                user_data,
                token_instance=self.context['token_instance'],
                coords_prepared=True,
            )
            return model_class.objects.create(user=user, **data)


class BaseProfilePatchSerializer(ModelSerializer):
    user_data = UserPatchSerializer(source='user', required=False)

    FORBIDDEN_FIELDS = (
        'is_approved',
        'is_rejected',
        'route_group',
        'review_status',
        'user',
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        errors = {}

        initial_data = getattr(self, 'initial_data', {}) or {}

        for field in self.FORBIDDEN_FIELDS:
            if field in initial_data:
                errors[field] = f"Você não tem permissão para alterar o campo '{field}'. Contate o suporte"

        user_data_input = initial_data.get('user_data', {})
        if isinstance(user_data_input, dict) and 'cpf' in user_data_input:
            errors.setdefault('user_data', {})['cpf'] = 'O CPF não pode ser alterado após a criação.'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def update(self, instance, validated_data):
        raw_user_data = validated_data.pop('user', None)
        user_data = prepare_user_coords(raw_user_data, instance=instance.user) if raw_user_data else None

        with transaction.atomic():
            if user_data:
                update_user_account(instance.user, user_data, coords_prepared=True)
            return super().update(instance, validated_data)
