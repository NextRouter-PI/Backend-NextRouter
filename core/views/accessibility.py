from rest_framework import viewsets

from core.models import Accessibility
from core.serializers import AccessibilitySerializer


class AccessibilityViewSet(viewsets.ModelViewSet):
    queryset = Accessibility.objects.all()
    serializer_class = AccessibilitySerializer
