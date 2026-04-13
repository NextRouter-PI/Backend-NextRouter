from rest_framework.viewsets import ModelViewSet

from core.models import Passenger
from core.serializers import PassengerSerializer


class PassengerViewSet(ModelViewSet):
    queryset = Passenger.objects.all()
    serializer_class = PassengerSerializer
