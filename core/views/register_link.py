from rest_framework.viewsets import ModelViewSet

from core.models import Register_Link
from core.serializers import Register_LinkSerializer


class Register_LinkViewSet(ModelViewSet):
    queryset = Register_Link.objects.all()
    serializer_class = Register_LinkSerializer
