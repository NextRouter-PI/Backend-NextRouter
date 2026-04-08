from rest_framework.serializers import ModelSerializer

from core.models import Company_Profile


class Company_ProfileSerializer(ModelSerializer):
    class Meta:
        model = Company_Profile
        fields = '__all__'
