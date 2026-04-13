from rest_framework.serializers import ModelSerializer

from core.models import Register_Link


class Register_LinkSerializer(ModelSerializer):
    class Meta:
        model = Register_Link
        fields = '__all__'
