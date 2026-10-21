from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from app.permissions import IsCompany, IsTravelDriverOrCompanyOwner
from authenticator.models.company import Company
from authenticator.models.passenger import Passenger
from router.models.confirm_passenger_route import ConfirmPassengerRoute
from router.models.travel import Travel
from router.serializers.travel import (
    TravelCreateSerializer,
    TravelListAndRetrieveSerializer,
    TravelLocationSerializer,
)


class TravelViewSet(ModelViewSet):
    queryset = Travel.objects.all()
    # A edição da viagem é feita pelas ações start/finish/location, não por PATCH genérico.
    http_method_names = ('get', 'post', 'patch')
    filterset_fields = ('company', 'driver', 'path', 'status')

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsCompany]
        elif self.action in {'start', 'finish', 'update_location', 'partial_update'}:
            permission_classes = [IsAuthenticated, IsTravelDriverOrCompanyOwner]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'create':
            return TravelCreateSerializer
        if self.action == 'update_location':
            return TravelLocationSerializer
        return TravelListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = Travel.objects.select_related(
            'company', 'company__user', 'driver', 'driver__user', 'path', 'path__route_group'
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
            Q(company__user=user) | Q(driver__user=user) | Q(path__route_group__passengers__user=user)
        ).distinct()

    def perform_create(self, serializer):
        path = serializer.validated_data['path']
        travel = serializer.save(company=Company.objects.get(pk=path.route_group.company_id))
        self._create_passenger_confirmations(travel)

    def _create_passenger_confirmations(self, travel):
        passengers = Passenger.objects.filter(route_group=travel.path.route_group, is_approved=True)
        ConfirmPassengerRoute.objects.bulk_create(
            [ConfirmPassengerRoute(travel=travel, user=passenger.user) for passenger in passengers],
            ignore_conflicts=True,
        )

    def _change_status(self, travel, expected_status, new_status, timestamp_field):
        if travel.status != expected_status:
            return Response(
                {'detail': f'Ação inválida para uma viagem com status "{travel.get_status_display()}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        travel.status = new_status
        setattr(travel, timestamp_field, timezone.now())
        travel.save(update_fields=['status', timestamp_field])

        return Response(TravelListAndRetrieveSerializer(travel).data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: TravelListAndRetrieveSerializer})
    @action(detail=True, methods=['patch'])
    def start(self, request, pk=None):
        return self._change_status(self.get_object(), Travel.Status.SCHEDULED, Travel.Status.IN_PROGRESS, 'started_at')

    @extend_schema(request=None, responses={200: TravelListAndRetrieveSerializer})
    @action(detail=True, methods=['patch'])
    def finish(self, request, pk=None):
        return self._change_status(
            self.get_object(), Travel.Status.IN_PROGRESS, Travel.Status.FINISHED, 'finished_at'
        )

    @extend_schema(responses={200: TravelListAndRetrieveSerializer})
    @action(detail=True, methods=['patch'], url_path='location')
    def update_location(self, request, pk=None):
        travel = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if travel.status != Travel.Status.IN_PROGRESS:
            return Response(
                {'detail': 'A localização só pode ser enviada durante uma viagem em andamento.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        travel.current_latitude = serializer.validated_data['latitude']
        travel.current_longitude = serializer.validated_data['longitude']
        travel.location_updated_at = timezone.now()
        travel.save(update_fields=['current_latitude', 'current_longitude', 'location_updated_at'])

        return Response(TravelListAndRetrieveSerializer(travel).data, status=status.HTTP_200_OK)
