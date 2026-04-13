from rest_framework.serializers import ModelSerializer

from core.models import Route_Group


class Route_GroupSerializer(ModelSerializer):
    class Meta:
        model = Route_Group
        fields = '__all__'