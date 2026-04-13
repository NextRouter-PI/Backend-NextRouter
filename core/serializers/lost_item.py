from rest_framework.serializers import ModelSerializer

from core.models import Lost_Item


class Lost_ItemSerializer(ModelSerializer):
    class Meta:
        model = Lost_Item
        fields = '__all__'
