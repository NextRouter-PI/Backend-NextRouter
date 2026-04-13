from rest_framework.viewsets import ModelViewSet

from core.models import Route
from core.serializers import RouteSerializer


class RouteViewSet(ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
