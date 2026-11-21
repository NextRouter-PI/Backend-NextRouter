from django.db.models import Q
from django.shortcuts import get_object_or_404

from modules.transport.access import companies_for, travels_for
from modules.transport.api.serializers.history import (
    CustodyInput,
    LostItemInput,
    LostItemSerializer,
    RatingInput,
    RatingSerializer,
)
from modules.transport.models import DriverRating, LostItem
from modules.transport.services.history import rate_driver, report_lost_item, transition_lost_item
from shared.domain_api import DomainViewSet, domain_action, domain_resource


@domain_resource('Histórico', 'avaliações das suas viagens')
class RatingViewSet(DomainViewSet):
    queryset = DriverRating.objects.none()
    serializer_class = RatingSerializer
    write_serializer_class = RatingInput
    filterset_fields = ('travel', 'driver')

    def get_scoped_queryset(self, user):
        return (
            DriverRating.objects
            .filter(travel__in=travels_for(user))
            .filter(Q(passenger=user) | Q(driver__user=user) | Q(travel__company__in=companies_for(user)))
            .order_by('-pk')
        )

    def create(self, request):
        data = self.input(RatingInput)
        get_object_or_404(travels_for(request.user), pk=data['travel_id'])
        return self.respond(rate_driver(actor_id=request.user.pk, **data), status=201)


@domain_resource('Histórico', 'objetos perdidos')
class LostItemViewSet(DomainViewSet):
    queryset = LostItem.objects.none()
    serializer_class = LostItemSerializer
    write_serializer_class = LostItemInput
    filterset_fields = ('travel', 'status')

    def get_scoped_queryset(self, user):
        return (
            LostItem.objects
            .filter(travel__in=travels_for(user))
            .filter(Q(user=user) | Q(travel__driver__user=user) | Q(travel__company__in=companies_for(user)))
            .prefetch_related('events')
            .distinct()
            .order_by('-pk')
        )

    def create(self, request):
        data = self.input(LostItemInput)
        get_object_or_404(travels_for(request.user), pk=data['travel_id'])
        return self.respond(report_lost_item(actor_id=request.user.pk, **data), status=201)

    @domain_action('Registre encontrado ou devolvido sem reabertura', request=CustodyInput, response=LostItemSerializer)
    def transition(self, request, pk=None):
        return self.respond(
            transition_lost_item(actor_id=request.user.pk, item_id=self.get_object().pk, **self.input(CustodyInput))
        )
