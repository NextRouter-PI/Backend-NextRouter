from rest_framework.viewsets import ModelViewSet

from core.models import Confirmed_Passenger
from core.serializers import Confirmed_PassengerSerializer


class Confirmed_PassengerViewSet(ModelViewSet):
    queryset = Confirmed_Passenger.objects.all()
    serializer_class = Confirmed_PassengerSerializer
