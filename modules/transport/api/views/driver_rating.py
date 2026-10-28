from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from modules.transport.api.serializers.driver_rating import (
    DriverRatingCreateSerializer,
    DriverRatingListAndRetrieveSerializer,
)
from modules.transport.models.driver_rating import DriverRating
from shared.openapi import document_viewset


@document_viewset(
    'Avaliações',
    'avaliação de motorista',
    'avaliações de motorista',
    read='Autor, motorista aprovado e empresa aprovada da viagem consultam avaliações; administrador vê todas.',
    create='Aluno com presença confirmada avalia o motorista uma vez por viagem finalizada; nota de 1 a 5.',
    change='Avaliações não permitem edição ou exclusão pela API.',
    read_response=DriverRatingListAndRetrieveSerializer,
    create_response=DriverRatingCreateSerializer,
)
class DriverRatingViewSet(ModelViewSet):
    queryset = DriverRating.objects.all()
    http_method_names = ('get', 'post')
    permission_classes = (IsAuthenticated,)
    filterset_fields = ('driver', 'travel')

    def get_serializer_class(self):
        if self.action == 'create':
            return DriverRatingCreateSerializer
        return DriverRatingListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = DriverRating.objects.select_related('driver__user', 'passenger', 'travel', 'travel__company')

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
            Q(passenger=user)
            | Q(driver__user=user, driver__is_approved=True)
            | Q(travel__company__user=user, travel__company__is_approved=True)
        ).distinct()
