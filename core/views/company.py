from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet

from core.models import Empresa
from core.serializers import EmpresaSerializer, RegistroEmpresaSerializer


class EmpresaViewSet(ModelViewSet):
    queryset = Empresa.objects.all().order_by('id')
    serializer_class = EmpresaSerializer


class RegistroEmpresaView(CreateAPIView):
    serializer_class = RegistroEmpresaSerializer
    permission_classes = [AllowAny]
