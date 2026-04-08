from rest_framework.viewsets import ModelViewSet

from core.models import Profile
from core.serializers import ProfileSerializer


class ProfileViewSet(ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
