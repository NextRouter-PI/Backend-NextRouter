from django.db import transaction
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from modules.accounts.api.serializers.user import UserCreateSerializer, UserPatchSerializer


class BaseProfileCreateSerializer(serializers.ModelSerializer):
    user_data = UserCreateSerializer(source='user')

    def create_user_instance(self, user_data):
        # `user_data` já foi validado pelo serializer aninhado (inclusive o código do e-mail, guardado em
        # context['token_instance']). Validar de novo falhava: os dados validados contêm instâncias
        # (ex.: a foto de perfil) e não os valores enviados pelo cliente.
        return UserCreateSerializer(context=self.context).create(user_data)


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

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)

        if user_data:
            # Os dados já foram validados pelo serializer aninhado; apenas aplica a atualização.
            UserPatchSerializer(instance.user, context=self.context).update(instance.user, user_data)

        return super().update(instance, validated_data)
