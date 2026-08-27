from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from authenticator.models.driver_rating import DriverRating
from authenticator.serializers.driver_rating import (
    DriverRatingCreateSerializer,
    DriverRatingListAndRetrieveSerializer,
)


class DriverRatingViewSet(ModelViewSet):
    queryset = DriverRating.objects.all()
    http_method_names = ('get', 'post')
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('driver',)

    def get_serializer_class(self):
        if self.action == 'create':
            return DriverRatingCreateSerializer
        return DriverRatingListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = DriverRating.objects.select_related('driver__user', 'passenger', 'travel')

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(Q(passenger=user) | Q(driver__user=user)).distinct()
