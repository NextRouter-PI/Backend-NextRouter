import logging
from typing import ClassVar

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from modules.organizations.models.company import Company
from modules.organizations.models.driver import Driver
from modules.organizations.models.passenger import Passenger
from modules.organizations.permissions import IsAssignedTravelDriver, IsCompany, IsCompanyOwner
from modules.transport.api.serializers.travel import (
    TravelCreateSerializer,
    TravelListAndRetrieveSerializer,
    TravelLocationSerializer,
)
from modules.transport.models.confirm_passenger_route import ConfirmPassengerRoute
from modules.transport.models.travel import Travel
from modules.transport.models.vehicle import Vehicle
from modules.transport.services import LocationRejected, save_travel_location
from shared.openapi import (
    RESP_400_VALIDATION,
    RESP_401_UNAUTHORIZED,
    RESP_403_FORBIDDEN,
    RESP_404_NOT_FOUND,
    document_viewset,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    create=extend_schema(
        tags=['Viagens'],
        summary='Cadastre uma viagem',
        description=(
            'Apenas empresa aprovada escolhe trajeto, motorista e veículo do próprio grupo; cria presenças pendentes.'
        ),
        responses={
            201: TravelCreateSerializer,
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
        },
        examples=[
            OpenApiExample('Viagem agendada', value={'path': 1, 'driver': 1, 'vehicle': 1}, request_only=True),
            OpenApiExample(
                'Viagem criada',
                value={'id': 1, 'company': 1, 'driver': 1, 'vehicle': 1, 'path': 1},
                response_only=True,
                status_codes=['201'],
            ),
        ],
    )
)
@document_viewset(
    'Viagens',
    'viagem',
    'viagens',
    read='Empresa, motorista e aluno aprovados veem viagens do próprio grupo; administrador vê todas.',
    create='Empresa aprovada escolhe trajeto, motorista aprovado e veículo ativo; presença começa não confirmada.',
    change='Viagens não aceitam PATCH genérico; use start, finish, cancel ou location conforme o papel.',
    read_response=TravelListAndRetrieveSerializer,
    create_response=TravelCreateSerializer,
    generic_patch=False,
)
class TravelViewSet(ModelViewSet):
    queryset = Travel.objects.all()
    # A edição da viagem é feita pelas ações start/finish/location, não por PATCH genérico.
    http_method_names = ('get', 'post', 'patch')
    filterset_fields: ClassVar[dict[str, list[str]]] = {
        'company': ['exact'],
        'driver': ['exact'],
        'path': ['exact'],
        'status': ['exact'],
        'started_at': ['date'],
    }

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsCompany]
        elif self.action in {'start', 'finish', 'update_location'}:
            permission_classes = [IsAuthenticated, IsAssignedTravelDriver]
        elif self.action == 'cancel':
            permission_classes = [IsAuthenticated, IsCompanyOwner]
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
            'company', 'company__user', 'driver', 'driver__user', 'path', 'path__route_group', 'vehicle'
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
            Q(company__user=user, company__is_approved=True)
            | Q(driver__user=user, driver__is_approved=True)
            | Q(path__route_group__passengers__user=user, path__route_group__passengers__is_approved=True)
        ).distinct()

    @transaction.atomic
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

        if new_status == Travel.Status.IN_PROGRESS:
            conflicts = Q(driver=travel.driver) | Q(vehicle=travel.vehicle)
            if Travel.objects.filter(conflicts, status=Travel.Status.IN_PROGRESS).exclude(pk=travel.pk).exists():
                return Response(
                    {'detail': 'Motorista ou veículo já está em uma viagem ativa.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        travel.status = new_status
        setattr(travel, timestamp_field, timezone.now())
        update_fields = ['status', timestamp_field]
        if new_status in {Travel.Status.FINISHED, Travel.Status.CANCELED}:
            travel.current_latitude = None
            travel.current_longitude = None
            travel.location_updated_at = None
            update_fields.extend(('current_latitude', 'current_longitude', 'location_updated_at'))
        travel.save(update_fields=update_fields)
        logger.info('travel_transition travel_id=%s status=%s', travel.pk, new_status)
        if new_status == Travel.Status.FINISHED:
            transaction.on_commit(
                lambda: async_to_sync(get_channel_layer().group_send)(f'travel_{travel.pk}', {'type': 'travel_closed'}),
                robust=True,
            )

        return Response(TravelListAndRetrieveSerializer(travel).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Viagens'],
        summary='Inicie a viagem',
        description=(
            'Somente motorista designado e aprovado. Muda scheduled para in_progress '
            'se empresa, grupo e veículo estiverem aptos.'
        ),
        request=None,
        responses={
            200: TravelListAndRetrieveSerializer,
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
            404: RESP_404_NOT_FOUND,
        },
    )
    @action(detail=True, methods=['patch'])
    @transaction.atomic
    def start(self, request, pk=None):
        travel = self.get_object()
        if not travel.vehicle_id:
            return Response({'detail': 'A viagem precisa de um veículo.'}, status=status.HTTP_400_BAD_REQUEST)
        driver = Driver.objects.select_for_update().get(pk=travel.driver_id)
        vehicle = Vehicle.objects.select_for_update().get(pk=travel.vehicle_id)
        travel = (
            Travel.objects
            .select_for_update()
            .select_related('company', 'driver', 'path__route_group')
            .get(pk=travel.pk)
        )
        self.check_object_permissions(request, travel)
        if not travel.company.is_approved:
            return Response({'detail': 'A empresa não está aprovada para operar.'}, status=status.HTTP_403_FORBIDDEN)
        if driver.route_group_id != travel.path.route_group_id or not driver.is_approved:
            return Response(
                {'detail': 'O motorista não está ativo neste grupo de rota.'}, status=status.HTTP_400_BAD_REQUEST
            )
        if (
            travel.vehicle_id != vehicle.pk
            or vehicle.status != Vehicle.Status.ACTIVE
            or vehicle.route_group_id != travel.path.route_group_id
            or vehicle.driver_id not in (None, travel.driver_id)
        ):
            return Response(
                {'detail': 'O veículo não está disponível neste grupo.'}, status=status.HTTP_400_BAD_REQUEST
            )
        if (
            vehicle.capacity is not None
            and travel.path.route_group.passengers.filter(is_approved=True).count() > vehicle.capacity
        ):
            return Response({'detail': 'Veículo com capacidade insuficiente.'}, status=status.HTTP_400_BAD_REQUEST)
        return self._change_status(travel, Travel.Status.SCHEDULED, Travel.Status.IN_PROGRESS, 'started_at')

    @extend_schema(
        tags=['Viagens'],
        summary='Finalize a viagem',
        description=(
            'Somente motorista designado e aprovado. Muda in_progress para finished, '
            'limpa localização e fecha conexões ao confirmar o commit.'
        ),
        request=None,
        responses={
            200: TravelListAndRetrieveSerializer,
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            404: RESP_404_NOT_FOUND,
        },
    )
    @action(detail=True, methods=['patch'])
    @transaction.atomic
    def finish(self, request, pk=None):
        travel = self.get_object()
        travel = Travel.objects.select_for_update().get(pk=travel.pk)
        self.check_object_permissions(request, travel)
        return self._change_status(travel, Travel.Status.IN_PROGRESS, Travel.Status.FINISHED, 'finished_at')

    @extend_schema(
        tags=['Viagens'],
        summary='Cancele a viagem',
        description='Somente empresa aprovada dona da viagem. Muda scheduled para canceled e limpa localização.',
        request=None,
        responses={
            200: TravelListAndRetrieveSerializer,
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            404: RESP_404_NOT_FOUND,
        },
    )
    @action(detail=True, methods=['patch'])
    @transaction.atomic
    def cancel(self, request, pk=None):
        travel = self.get_object()
        travel = Travel.objects.select_for_update().get(pk=travel.pk)
        self.check_object_permissions(request, travel)
        return self._change_status(travel, Travel.Status.SCHEDULED, Travel.Status.CANCELED, 'finished_at')

    @extend_schema(
        tags=['Viagens'],
        summary='Use as ações da viagem',
        description='PATCH genérico sempre responde 405; use start, finish, cancel ou location.',
        responses={405: OpenApiResponse(description='Atualização genérica de viagem não permitida.')},
    )
    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PATCH')

    @extend_schema(
        tags=['Viagens'],
        summary='Envie a localização da viagem',
        description=(
            'Somente motorista designado em viagem ativa. Valida coordenadas, horário e frequência; '
            'publica posição após commit para participantes aprovados.'
        ),
        request=TravelLocationSerializer,
        responses={
            200: TravelListAndRetrieveSerializer,
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            404: RESP_404_NOT_FOUND,
            429: OpenApiResponse(description='Atualização de localização enviada antes do intervalo mínimo.'),
        },
    )
    @action(detail=True, methods=['patch'], url_path='location')
    def update_location(self, request, pk=None):
        travel = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            save_travel_location(
                travel.pk,
                request.user.pk,
                serializer.validated_data['latitude'],
                serializer.validated_data['longitude'],
                serializer.validated_data.get('recorded_at'),
            )
        except LocationRejected as exc:
            return Response({'detail': str(exc)}, status=exc.status_code)
        travel.refresh_from_db()
        return Response(TravelListAndRetrieveSerializer(travel).data, status=status.HTTP_200_OK)
