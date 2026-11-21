from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404

from modules.organizations.access import companies_for
from modules.organizations.models import CompanyRouteGroup, HabitualRoute, PassengerGroupMembership
from modules.transport.api.serializers.configuration import (
    HabitualRouteInput,
    HabitualRouteSerializer,
    HabitualRouteUpdateInput,
)
from modules.transport.models import RecurringService
from modules.transport.services.configuration import configure_habitual_route
from shared.domain_api import DomainViewSet, domain_resource


@domain_resource('Configuração', 'rotas habituais e compartilhadas')
class HabitualRouteViewSet(DomainViewSet):
    queryset = HabitualRoute.objects.none()
    serializer_class = HabitualRouteSerializer
    write_serializer_class = HabitualRouteInput
    filterset_fields = ('route_group', 'kind')

    def get_scoped_queryset(self, user):
        if not user.is_authenticated or not user.is_active:
            return HabitualRoute.objects.none()
        ordered_services = RecurringService.objects.order_by('direction', 'target_time', 'pk')
        active_members = PassengerGroupMembership.objects.active_members().select_related(
            'membership__passenger__user',
            'membership__passenger__user__profile_picture',
            'transport_point',
        )
        return (
            HabitualRoute.objects
            .select_related('route_group__company', 'route_group__destination')
            .prefetch_related(
                Prefetch('route_group__services', queryset=ordered_services, to_attr='ordered_services'),
                Prefetch('passenger_memberships', queryset=active_members, to_attr='active_route_members'),
            )
            .filter(
                Q(route_group__company__in=companies_for(user))
                | Q(
                    kind=HabitualRoute.Kind.HABITUAL,
                    passenger_memberships__membership__passenger__user=user,
                    passenger_memberships__ended_at__isnull=True,
                    passenger_memberships__membership__status='active',
                    route_group__company__is_approved=True,
                    route_group__company__is_rejected=False,
                    route_group__company__user__is_active=True,
                )
                | Q(
                    kind=HabitualRoute.Kind.SHARED,
                    route_group__passenger_memberships__membership__passenger__user=user,
                    route_group__passenger_memberships__ended_at__isnull=True,
                    route_group__passenger_memberships__membership__status='active',
                    route_group__company__is_approved=True,
                    route_group__company__is_rejected=False,
                    route_group__company__user__is_active=True,
                )
            )
            .distinct()
            .order_by('route_group_id', 'kind', 'name', 'pk')
        )

    def create(self, request):
        data = self.input(HabitualRouteInput)
        group = get_object_or_404(
            CompanyRouteGroup, pk=data.pop('route_group_id'), company__in=companies_for(request.user)
        )
        return self.respond(
            configure_habitual_route(actor_id=request.user.pk, group_id=group.pk, **data),
            status=201,
        )

    def partial_update(self, request, pk=None):
        route = get_object_or_404(HabitualRoute, pk=pk, route_group__company__in=companies_for(request.user))
        serializer = HabitualRouteUpdateInput(data=request.data, partial=True, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        return self.respond(
            configure_habitual_route(
                actor_id=request.user.pk,
                group_id=route.route_group_id,
                route_id=route.pk,
                **serializer.to_service_kwargs(route),
            )
        )
