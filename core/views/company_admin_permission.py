from rest_framework.viewsets import ModelViewSet

from core.models import Company_Admin_Permission
from core.serializers import Company_Admin_PermissionSerializer


class Company_Admin_PermissionViewSet(ModelViewSet):
    queryset = Company_Admin_Permission.objects.all()
    serializer_class = Company_Admin_PermissionSerializer
