from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet

from core.models import Motorista
from core.serializers import MotoristaSerializer, RegistroMotoristaSerializer


class MotoristaViewSet(ModelViewSet):
    queryset = Motorista.objects.all().order_by('id')
    serializer_class = MotoristaSerializer


class RegistroMotoristaView(CreateAPIView):
    serializer_class = RegistroMotoristaSerializer
    permission_classes = [AllowAny]
