from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from modules.accounts.models import User, UserSession


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Normaliza o e-mail de forma case-insensitive antes da autenticação SimpleJWT."""

    def validate(self, attrs):
        email = attrs.get(self.username_field)
        if isinstance(email, str):
            normalized = email.strip().lower()
            stored_email = User.objects.by_email(normalized).values_list('email', flat=True).first()
            attrs[self.username_field] = stored_email or normalized
        return super().validate(attrs)


@extend_schema_serializer(component_name='UserSessionResponse')
class UserSessionSerializer(serializers.ModelSerializer):
    device = serializers.CharField(source='device_name', read_only=True)
    ip = serializers.IPAddressField(source='ip_address', allow_null=True, read_only=True)
    current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = ('id', 'device', 'ip', 'created_at', 'current')

    def get_current(self, obj) -> bool:
        current_jti = self.context.get('current_jti')
        return bool(current_jti and obj.access_jti == current_jti)
