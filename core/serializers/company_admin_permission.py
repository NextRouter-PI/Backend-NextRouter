from rest_framework.serializers import ModelSerializer

from core.models import Company_Admin_Permission


class Company_Admin_PermissionSerializer(ModelSerializer):
    class Meta:
        model = Company_Admin_Permission
        fields = '__all__'
