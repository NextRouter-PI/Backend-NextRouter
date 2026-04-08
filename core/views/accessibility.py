from rest_framework.viewsets import ModelViewSet

from core.models import Accessibility
from core.serializers import AccessibilitySerializer


class AccessibilityViewSet(ModelViewSet):
    queryset = Accessibility.objects.all()
    serializer_class = AccessibilitySerializer
