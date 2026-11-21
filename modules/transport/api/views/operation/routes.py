from modules.organizations.access import companies_for
from modules.transport.access import operational_travels_for, travels_for
from modules.transport.api.serializers.operation import (
    JobSerializer,
    PublicationSerializer,
    SnapshotSerializer,
    StopInput,
    StopSerializer,
)
from modules.transport.models import RouteOptimizationJob, RouteSnapshot, RouteStop, TravelPublication
from modules.transport.services.execution import handle_stop
from shared.domain_api import DomainViewSet, domain_action, domain_resource


@domain_resource('Percursos', 'snapshots de percursos')
class SnapshotViewSet(DomainViewSet):
    queryset = RouteSnapshot.objects.none()
    serializer_class = SnapshotSerializer
    filterset_fields = ('travel', 'state', 'change_request')

    def get_scoped_queryset(self, user):
        return RouteSnapshot.objects.filter(travel__in=operational_travels_for(user)).order_by('-pk')


@domain_resource('Percursos', 'publicações de viagens')
class PublicationViewSet(DomainViewSet):
    queryset = TravelPublication.objects.none()
    serializer_class = PublicationSerializer
    filterset_fields = ('travel', 'revision')

    def get_scoped_queryset(self, user):
        return TravelPublication.objects.filter(travel__in=travels_for(user)).order_by('-pk')


@domain_resource('Execução', 'paradas do percurso')
class StopViewSet(DomainViewSet):
    queryset = RouteStop.objects.none()
    serializer_class = StopSerializer
    filterset_fields = ('snapshot', 'state')

    def get_scoped_queryset(self, user):
        return (
            RouteStop.objects
            .filter(snapshot__travel__in=operational_travels_for(user))
            .prefetch_related('participants__participation__eligibility__passenger__user__profile_picture')
            .order_by('snapshot', 'position')
        )

    @domain_action('Avance a parada na ordem do percurso', request=StopInput, response=StopSerializer)
    def handle(self, request, pk=None):
        return self.respond(
            handle_stop(actor_id=request.user.pk, stop_id=self.get_object().pk, **self.input(StopInput))
        )


@domain_resource('Percursos', 'estado dos trabalhos de cálculo')
class JobViewSet(DomainViewSet):
    queryset = RouteOptimizationJob.objects.none()
    serializer_class = JobSerializer
    filterset_fields = ('snapshot', 'status')

    def get_scoped_queryset(self, user):
        return RouteOptimizationJob.objects.filter(
            snapshot__travel__company__in=companies_for(user), snapshot__isnull=False
        ).order_by('-pk')
