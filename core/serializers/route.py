from rest_framework.serializers import ModelSerializer

from core.models import Route


class RouteSerializer(ModelSerializer):
    class Meta:
        model = Route
        fields = '__all__'
