from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet

from core.models import Passageiro
from core.serializers import PassageiroSerializer, RegistroPassageiroSerializer


class PassageiroViewSet(ModelViewSet):
    queryset = Passageiro.objects.all().order_by('id')
    serializer_class = PassageiroSerializer


class RegistroPassageiroView(CreateAPIView):
    serializer_class = RegistroPassageiroSerializer
    permission_classes = [AllowAny]
