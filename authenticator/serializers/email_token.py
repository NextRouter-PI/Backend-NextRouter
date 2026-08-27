from rest_framework import serializers

from authenticator.mixins.tokens import TokenValidatorMixin
from authenticator.models.email_token import EmailToken


class EmailTokenCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailToken
        fields = (
            'email',
            'token_type',
        )


class EmailTokenVerifySerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=True, max_length=6)

    class Meta:
        model = EmailToken
        fields = (
            'email',
            'code',
            'token_type',
        )


class PasswordResetSerializer(TokenValidatorMixin, serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=True, max_length=6)
    password = serializers.CharField(required=True, write_only=True, min_length=6)

    def validate(self, attrs):
        token = self.validate_token(attrs['email'], attrs['code'], token_type='new-password')
        self.context['token_instance'] = token
        return attrs
