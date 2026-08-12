from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from authenticator.models.email_token import EmailToken
from authenticator.models.user import User
from authenticator.validators.cpf import validate_cpf
from uploader.models import Image
from uploader.serializers import ImageSerializer, ImageUploadSerializer

CEP_LENGTH = 9


class TokenValidatorMixin:
    def validate_token(self, email, code, token_type):
        if not email:
            raise serializers.ValidationError(
                {'email': 'O e-mail é obrigatório para validar o código.'},
            )

        token = (
            EmailToken.objects
            .filter(email=email, token_type=token_type)
            .order_by(
                '-created_at',
            )
            .first(),
        )

        if not token or not check_password(
            code,
            token.token_hash,
        ):
            raise serializers.ValidationError(
                {'code': 'Código inválido ou inexistente.'},
            )

        if token.consumed:
            raise serializers.ValidationError(
                {'code': 'Este código já foi utilizado.'},
            )

        return token


class UserListAndRetriveSerializer(ModelSerializer):
    profile_picture_data = ImageSerializer(source='profile_picture')

    class Meta:
        model = User
        fields = (
            'id',
            'name',
            'profile_picture_data',
            'cep',
        )


class UserCreateSerializer(ModelSerializer, TokenValidatorMixin):
    password = serializers.CharField(write_only=True, required=True)
    profile_picture = ImageUploadSerializer('profile_picture', required=False)
    code = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(required=True)
    cpf = serializers.CharField(required=True, validators=[validate_cpf])

    class Meta:
        model = User
        fields = (
            'code',
            'email',
            'name',
            'password',
            'cep',
            'phone',
            'profile_picture',
            'cpf',
            'birthday',
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        email = attrs.get('email')
        code = attrs.get('code')

        token = self.validate_token(email, code, token_type='new-user')

        self.context['token_instance'] = token
        return attrs

    # Validando por aqui afim de não precisar importar cada validador do Django,
    # e inserir no validators=[] do campo password no serializer.
    def validate_password(self, value):
        validate_password(value)
        return value

        return value

    def create(self, validated_data):
        validated_data.pop('code', None)
        profile_picture_data = validated_data.pop('profile_picture', None)

        user_name = validated_data.get('name', '')
        user_cpf = validated_data.get('cpf', '')
        pic_instance = None

        if profile_picture_data:
            profile_picture_data['description'] = f'Foto de {user_name} ({user_cpf})'
            pic_instance = Image.objects.create(**profile_picture_data)

        user = User.objects.create_user(**validated_data, profile_picture=pic_instance)

        token = self.context.get('token_instance')
        if token:
            token.consumed = True
            token.save()

        return user


class UserPatchSerializer(UserCreateSerializer):
    password = serializers.CharField(write_only=True, required=False)
    code = serializers.CharField(write_only=True, required=False)
    current_password = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(required=False)
    cpf = serializers.CharField(required=False, validators=[validate_cpf])

    class Meta:
        model = User
        fields = (
            'code',
            'email',
            'password',
            'current_password',
            'name',
            'cep',
            'phone',
            'profile_picture',
        )

    def validate(self, attrs):
        initial_data = getattr(self, 'initial_data', {}) or {}

        if 'cpf' in initial_data:
            raise serializers.ValidationError({
                'cpf': 'Você não tem permissão para alterar o campo CPF. Contate o suporte.'
            })

        user = self.instance
        new_email = attrs.get('email')

        if user and new_email and new_email != user.email:
            if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                raise serializers.ValidationError({'email': 'Já existe um usuário cadastrado com este e-mail.'})

            current_pw = attrs.get('current_password')
            if not current_pw or not user.check_password(current_pw):
                raise serializers.ValidationError({'current_password': 'Senha atual incorreta.'})

            code = attrs.get('code')
            if not code:
                raise serializers.ValidationError({
                    'code': 'O código de verificação é obrigatório para alterar o e-mail.'
                })

            token = self.validate_token(new_email, code, token_type='new-email')
            self.context['token_instance'] = token

        elif 'password' in attrs:
            code = attrs.get('code')
            if not code:
                raise serializers.ValidationError({
                    'code': 'O código de verificação é obrigatório para alterar a senha.'
                })

            email_for_token = user.email if user else attrs.get('email')
            token = self.validate_token(email_for_token, code, token_type='new-password')
            self.context['token_instance'] = token

        return super(UserCreateSerializer, self).validate(attrs)

    def update(self, instance, validated_data):
        validated_data.pop('code', None)
        validated_data.pop('current_password', None)
        profile_picture_data = validated_data.pop('profile_picture', None)
        if profile_picture_data:
            profile_picture_data['description'] = f'Foto atualizada de {validated_data.get("name", instance.name)}'
            instance.profile_picture = Image.objects.create(**profile_picture_data)

        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)

        user = super(UserCreateSerializer, self).update(instance, validated_data)

        token = self.context.get('token_instance')
        if token:
            token.consumed = True
            token.save()

        return user


class BaseProfileCreateSerializer(serializers.ModelSerializer):
    user_data = UserCreateSerializer(source='user')

    def create_user_instance(self, user_data):
        user_serializer = UserCreateSerializer(data=user_data)
        user_serializer.is_valid(raise_exception=True)
        return user_serializer.save()


class BaseProfilePatchSerializer(ModelSerializer):
    user_data = UserPatchSerializer(source='user', required=False)

    FORBIDDEN_FIELDS = (
        'is_approved',
        'group_route',
        'user',
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        errors = {}

        for field in self.FORBIDDEN_FIELDS:
            if field in self.initial_data:
                errors[field] = f"Você não tem permissão para alterar o campo '{field}'."

        user_data_input = self.initial_data.get('user_data', {})
        if isinstance(user_data_input, dict) and 'cpf' in user_data_input:
            errors.setdefault('user_data', {})['cpf'] = 'O CPF não pode ser alterado após a criação.'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)

        if user_data:
            user_instance = getattr(instance, 'user', None)

            if not user_instance:
                raise serializers.ValidationError({'user_data': 'Usuário associado a este perfil não foi encontrado.'})

            user_serializer = UserPatchSerializer(
                user_instance,
                data=user_data,
                partial=True,
                context=self.context,
            )
            user_serializer.is_valid(raise_exception=True)
            user_serializer.save()

        return super().update(instance, validated_data)
