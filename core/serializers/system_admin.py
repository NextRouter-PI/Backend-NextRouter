from rest_framework.serializers import ModelSerializer

from core.models import System_Admin


class System_AdminSerializer(ModelSerializer):
    class Meta:
        model = System_Admin
        fields = '__all__'
