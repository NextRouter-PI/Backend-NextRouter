from rest_framework.serializers import ModelSerializer

from core.models import Company_Registration_Request


class Company_Registration_RequestSerializer(ModelSerializer):
    class Meta:
        model = Company_Registration_Request
        fields = '__all__'
