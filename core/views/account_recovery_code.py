from rest_framework.viewsets import ModelViewSet

from core.models import Account_Recovery_Code
from core.serializers import Account_Recovery_CodeSerializer


class Account_Recovery_CodeViewSet(ModelViewSet):
    queryset = Account_Recovery_Code.objects.all()
    serializer_class = Account_Recovery_CodeSerializer
