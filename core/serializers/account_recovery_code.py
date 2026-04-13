from rest_framework.serializers import ModelSerializer

from core.models import Account_Recovery_Code


class Account_Recovery_CodeSerializer(ModelSerializer):
    class Meta:
        model = Account_Recovery_Code
        fields = '__all__'
