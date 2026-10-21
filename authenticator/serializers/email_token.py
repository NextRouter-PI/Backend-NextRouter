from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from authenticator.mixins.tokens import TokenValidatorMixin
from authenticator.models.email_token import EmailToken
from authenticator.models.user import User


class EmailTokenCreateSerializer(serializers.ModelSerializer):
    token_type = serializers.ChoiceField(choices=EmailToken.TokenType.choices)

    class Meta:
        model = EmailToken
        fields = (
            'email',
            'token_type',
        )

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        new_account = attrs['token_type'] in {EmailToken.TokenType.NEW_USER, EmailToken.TokenType.NEW_EMAIL}
        if new_account and User.objects.filter(email__iexact=attrs['email']).exists():
            raise serializers.ValidationError({'email': 'Já existe um usuário cadastrado com este e-mail.'})

        return attrs


class EmailTokenVerifySerializer(TokenValidatorMixin, serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True, max_length=6)
    token_type = serializers.ChoiceField(choices=EmailToken.TokenType.choices)

    def validate(self, attrs):
        self.validate_token(attrs['email'], attrs['code'], token_type=attrs['token_type'])
        return attrs


class PasswordResetSerializer(TokenValidatorMixin, serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True, max_length=6)
    password = serializers.CharField(required=True, write_only=True)

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        token = self.validate_token(attrs['email'], attrs['code'], token_type=EmailToken.TokenType.NEW_PASSWORD)
        self.context['token_instance'] = token
        return attrs
