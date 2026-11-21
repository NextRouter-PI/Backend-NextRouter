from django.contrib.auth.password_validation import validate_password
from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from rest_framework.validators import UniqueValidator

from modules.accounts.mixins.tokens import TokenValidatorMixin
from modules.accounts.models import EmailToken, User
from modules.accounts.services import create_user_account, update_user_account
from modules.accounts.validators.cpf import validate_cpf
from modules.uploads.api.serializers import ImageSerializer
from modules.uploads.models import Image


@extend_schema_serializer(component_name='UserListAndRetrive')
class UserReadSerializer(ModelSerializer):
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


UserListAndRetriveSerializer = UserReadSerializer


class _ProfilePictureFieldMixin(serializers.Serializer):
    profile_picture = serializers.SlugRelatedField(
        slug_field='attachment_key',
        queryset=Image.objects.all(),
        required=False,
        allow_null=True,
    )


class UserCreateSerializer(_ProfilePictureFieldMixin, ModelSerializer, TokenValidatorMixin):
    password = serializers.CharField(write_only=True, required=True)
    code = serializers.CharField(write_only=True, required=True)
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
    cpf = serializers.CharField(required=True, validators=[validate_cpf])
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False, allow_null=True)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False, allow_null=True)

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
            'latitude',
            'longitude',
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

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('Formato de código inválido.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        code = attrs.get('code')
        if not code:
            raise serializers.ValidationError({'code': 'O código é obrigatório.'})

        token = self.validate_token(attrs.get('email'), code, token_type=EmailToken.TokenType.NEW_USER)
        validate_password(
            attrs['password'], user=User(**{key: attrs[key] for key in ('email', 'name') if key in attrs})
        )
        self.context['token_instance'] = token
        return attrs

    def create(self, validated_data):
        return create_user_account(validated_data, token_instance=self.context['token_instance'])


class UserPatchSerializer(_ProfilePictureFieldMixin, ModelSerializer):
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

    def update(self, instance: User, validated_data):
        return update_user_account(instance, validated_data)
