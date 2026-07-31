from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models import User
from uploader.models import Image
from uploader.serializers import ImageSerializer, ImageUploadSerializer

CEP_LENGTH = 9


class UserListAndRetriveSerializer(ModelSerializer):
    profile_picture_data = ImageSerializer(source='profile_picture')

    class Meta:
        model = User
        fields = ['id', 'name', 'profile_picture_data', 'cep']


class UserCreateSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    profile_picture = ImageUploadSerializer('profile_picture', required=False)

    def create(self, validated_data):
        profile_picture_data = validated_data.pop('profile_picture', None)
        user_name = validated_data.get('name', '')
        user_cpf = validated_data.get('cpf', '')
        pic_instance = None

        if profile_picture_data:
            profile_picture_data['description'] = f'Foto de {user_name} ({user_cpf})'

            pic_instance = Image.objects.create(**profile_picture_data)

        return User.objects.create_user(**validated_data, profile_picture=pic_instance)

    class Meta:
        model = User
        fields = [
            'email',
            'name',
            'password',
            'cep',
            'phone',
            'profile_picture',
            'cpf',
            'birthday',
        ]


class BaseProfileCreateSerializer(serializers.ModelSerializer):
    user_data = UserCreateSerializer(source='user')

    def create_user_instance(self, user_data):
        # Utiliza a lógica do próprio UserCreateSerializer para criar o usuário corretamente
        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        return user_serializer.save()


class UserPatchSerializer(UserCreateSerializer):
    class Meta:
        model = User
        fields = ['email', 'name', 'cep', 'phone', 'profile_picture']

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if 'cpf' in self.initial_data:
            raise serializers.ValidationError({
                'cpf': 'Você não tem permissão para alterar o campo CPF. Contate o suporte.'
            })

        return attrs


class BaseProfilePatchSerializer(ModelSerializer):
    user_data = UserPatchSerializer(source='user', required=False)

    # Campos que o perfil (Passageiro/Motorista) não pode alterar via PATCH
    FORBIDDEN_FIELDS = ['is_approved', 'group_route', 'user']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        errors = {}

        # 1. Valida campos proibidos no payload raiz
        for field in self.FORBIDDEN_FIELDS:
            if field in self.initial_data:
                errors[field] = f"Você não tem permissão para alterar o campo '{field}'."

        # 2. Valida se tentaram passar o CPF dentro de user_data
        user_data_input = self.initial_data.get('user_data', {})
        if isinstance(user_data_input, dict) and 'cpf' in user_data_input:
            errors.setdefault('user_data', {})['cpf'] = 'O CPF não pode ser alterado após a criação.'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def update(self, instance, validated_data):
        # Extrai os dados do Usuário (reparar no 'user', pois source='user')
        user_data = validated_data.pop('user', None)

        # Atualiza a instância do User associado, se houver dados
        if user_data:
            user_serializer = UserPatchSerializer(instance.user, data=user_data, partial=True)
            user_serializer.is_valid(raise_exception=True)
            user_serializer.save()

        # Atualiza a instância principal (Passenger ou Driver)
        return super().update(instance, validated_data)
