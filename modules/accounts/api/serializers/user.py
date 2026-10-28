from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from rest_framework.validators import UniqueValidator

from modules.accounts.mixins.tokens import TokenValidatorMixin, consume_email_token
from modules.accounts.models.user import User
from modules.accounts.validators.cpf import validate_cpf
from modules.uploads.api.serializers import ImageSerializer
from modules.uploads.models import Image


class UserListAndRetriveSerializer(ModelSerializer):
    profile_picture_data = ImageSerializer(
        source='profile_picture',
        read_only=True,
    )

    class Meta:
        model = User
        fields = (
            'id',
            'name',
            'email',
            'phone',
            'cpf',
            'birthday',
            'profile_picture_data',
            'cep',
            'street',
            'number',
            'complement',
            'neighborhood',
            'city',
            'state',
            'latitude',
            'longitude',
            'geocoded_at',
            'created_at',
        )


class UserCreateSerializer(ModelSerializer, TokenValidatorMixin):
    password = serializers.CharField(
        write_only=True,
        required=True,
    )
    profile_picture = serializers.SlugRelatedField(
        slug_field='attachment_key',
        queryset=Image.objects.all(),
        required=False,
        allow_null=True,
    )
    code = serializers.CharField(
        write_only=True,
        required=True,
    )
    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                lookup='iexact',
                message='Já existe um usuário cadastrado com este e-mail.',
            ),
        ],
    )
    cpf = serializers.CharField(
        required=True,
        validators=[validate_cpf],
    )

    class Meta:
        model = User
        fields = (
            'code',
            'email',
            'name',
            'password',
            'cep',
            'street',
            'number',
            'complement',
            'neighborhood',
            'city',
            'state',
            'phone',
            'profile_picture',
            'cpf',
            'birthday',
        )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_cpf(self, value):
        # O front-end envia o CPF com máscara (000.000.000-00), mas a coluna guarda só os 11 dígitos.
        cpf = ''.join(filter(str.isdigit, value))
        if User.objects.filter(cpf=cpf).exists():
            raise serializers.ValidationError('Já existe um usuário cadastrado com este CPF.')
        return cpf

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('Formato de código inválido.')

        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        code = attrs.get('code')

        if not code:
            raise serializers.ValidationError({'code': 'O código é obrigatório.'})

        email = attrs.get('email')

        token = self.validate_token(email, code, token_type='new-user')

        self.context['token_instance'] = token

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('code', None)
        consume_email_token(self.context['token_instance'])

        pic_instance = validated_data.pop('profile_picture', None)
        if pic_instance:
            # A descrição da foto é exibida para outros usuários: não incluir o CPF.
            pic_instance.description = f'Foto de {validated_data.get("name", "")}'
            pic_instance.save(update_fields=['description'])

        user = User.objects.create_user(**validated_data, profile_picture=pic_instance)

        return user


class UserPatchSerializer(UserCreateSerializer):
    password = None
    email = None
    code = None
    cpf = None

    class Meta:
        model = User
        fields = (
            'name',
            'cep',
            'street',
            'number',
            'complement',
            'neighborhood',
            'city',
            'state',
            'phone',
            'birthday',
            'profile_picture',
        )

    def validate(self, attrs):
        initial_data = getattr(self, 'initial_data', {}) or {}
        if 'cpf' in initial_data:
            raise serializers.ValidationError({
                'cpf': 'Você não tem permissão para alterar o campo CPF. Contate o suporte.'
            })
        return attrs

    @transaction.atomic
    def update(self, instance: User, validated_data):
        if 'profile_picture' in validated_data:
            new_pic_instance = validated_data.pop('profile_picture')
            old_pic_instance = instance.profile_picture

            if old_pic_instance and old_pic_instance != new_pic_instance:
                old_pic_instance.delete()

            if new_pic_instance:
                new_pic_instance.description = f'Foto de {validated_data.get("name", instance.name)}'
                new_pic_instance.save(update_fields=['description'])

            instance.profile_picture = new_pic_instance

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


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
