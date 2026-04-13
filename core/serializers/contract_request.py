from rest_framework.serializers import ModelSerializer

from core.models import Contract_Request


class Contract_RequestSerializer(ModelSerializer):
    class Meta:
        model = Contract_Request
        fields = '__all__'
