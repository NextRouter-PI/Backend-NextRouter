from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsSelfOrCompany
from core.models.passenger import Passenger
from core.serializers.passenger import PassengerSerializer


class PassengerViewSet(ModelViewSet):
    queryset = Passenger.objects.all()
    serializer_class = PassengerSerializer
    permission_classes = [IsAuthenticated, IsSelfOrCompany]
