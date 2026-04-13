from rest_framework.serializers import ModelSerializer

from core.models import Company_Admin


class Company_AdminSerializer(ModelSerializer):
    class Meta:
        model = Company_Admin
        fields = '__all__'
