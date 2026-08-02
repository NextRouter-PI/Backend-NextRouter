from rest_framework import serializers

from authenticator.models.email_token import EmailToken


class EmailTokenCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailToken
        fields = ['email', 'token_type']


class EmailTokenVerifySerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=True, max_length=6)

    class Meta:
        model = EmailToken
        fields = ['email', 'code', 'token_type']
