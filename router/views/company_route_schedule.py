from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsScheduleOwner
from router.models.company_route_schedule import CompanyRouteSchedule
from router.serializers.company_route_schedule import (
    CompanyRouteScheduleCreateSerializer,
    CompanyRouteScheduleListAndRetrieveSerializer,
    CompanyRouteSchedulePatchSerializer,
)


class CompanyRouteScheduleViewSet(ModelViewSet):
    queryset = CompanyRouteSchedule.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_fields = ('route_group',)

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsCompany]
        elif self.action in {'partial_update', 'destroy'}:
            permission_classes = [IsAuthenticated, IsCompany, IsScheduleOwner]
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return CompanyRouteScheduleCreateSerializer
        elif self.action == 'partial_update':
            return CompanyRouteSchedulePatchSerializer
        return CompanyRouteScheduleListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = CompanyRouteSchedule.objects.select_related(
            'route_group',
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return (
            queryset
            .filter(
                Q(route_group__company__user=user)
                | Q(route_group__drivers__user=user)
                | Q(route_group__passengers__user=user)
            )
            .distinct()
            .order_by('route_group', 'go_hour')
        )
