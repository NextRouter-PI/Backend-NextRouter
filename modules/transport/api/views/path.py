from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from modules.organizations.models.passenger import Passenger
from modules.organizations.permissions import IsCompany, IsPathOwner
from modules.transport.api.serializers.path import (
    OptimizedPathResponseSerializer,
    OptimizePathSerializer,
    PathCreateSerializer,
    PathListAndRetrieveSerializer,
    PathPatchSerializer,
)
from modules.transport.models.path import Path
from modules.transport.models.route_optimization_job import RouteOptimizationJob
from modules.transport.models.travel import Travel
from modules.transport.optimization import process_optimization
from modules.transport.osrm import OSRMError
from shared.geocoding import GeocodingError
from shared.openapi import (
    RESP_400_VALIDATION,
    RESP_401_UNAUTHORIZED,
    RESP_403_FORBIDDEN,
    RESP_404_NOT_FOUND,
    RESP_503_UNAVAILABLE,
    document_viewset,
)


@document_viewset(
    'Rotas/OSRM',
    'trajeto',
    'trajetos',
    read='Empresa, motorista e aluno aprovados consultam trajetos do grupo; dados de paradas são limitados por papel.',
    create='Empresa aprovada define trajeto do próprio grupo; não sugere rotas nem aloca motoristas.',
    change='Apenas empresa aprovada dona do grupo altera/exclui; alterações invalidam a otimização anterior.',
    read_response=PathListAndRetrieveSerializer,
    create_response=PathCreateSerializer,
    update_response=PathPatchSerializer,
)
class PathViewSet(ModelViewSet):
    queryset = Path.objects.all()
    http_method_names = ('get', 'post', 'patch', 'delete')
    filterset_fields = ('route_group',)

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticated, IsCompany]
        elif self.action in {'partial_update', 'destroy', 'optimize', 'optimization'}:
            permission_classes = [IsAuthenticated, IsCompany, IsPathOwner]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'optimize':
            return OptimizePathSerializer
        if self.action == 'create':
            return PathCreateSerializer
        elif self.action == 'partial_update':
            return PathPatchSerializer
        return PathListAndRetrieveSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = Path.objects.select_related(
            'route_group',
            'route_group__company',
        )

        if user.is_staff or user.is_superuser:
            return queryset.all()

        return queryset.filter(
            Q(route_group__company__user=user, route_group__company__is_approved=True)
            | Q(
                route_group__drivers__user=user,
                route_group__drivers__is_approved=True,
                route_group__company__is_approved=True,
            )
            | Q(
                route_group__passengers__user=user,
                route_group__passengers__is_approved=True,
                route_group__company__is_approved=True,
            ),
        ).distinct()

    @extend_schema(
        tags=['Rotas/OSRM'],
        summary='Otimize o trajeto',
        description=(
            'Apenas empresa aprovada dona do trajeto. Recebe início, passageiros aprovados ou paradas explícitas '
            'e fim opcional; OSRM ordena as paradas, não sugere rotas nem motoristas. Síncrono por padrão (200); '
            'async_mode cria job (202). Não altera rota durante viagem ativa ou em falha de OSRM.'
        ),
        request=OptimizePathSerializer,
        responses={
            200: OptimizedPathResponseSerializer,
            202: inline_serializer(
                'RouteJobAccepted', fields={'job_id': serializers.IntegerField(), 'status': serializers.CharField()}
            ),
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
            404: RESP_404_NOT_FOUND,
            422: OpenApiResponse(description='OSRM não encontrou um trajeto válido para as paradas escolhidas.'),
            502: OpenApiResponse(description='Serviço OSRM respondeu com erro.'),
            503: RESP_503_UNAVAILABLE,
        },
        examples=[
            OpenApiExample(
                'Paradas escolhidas',
                value={
                    'start': {'latitude': -26.3, 'longitude': -48.8},
                    'stops': [{'latitude': -26.31, 'longitude': -48.81, 'label': 'Parada fictícia'}],
                    'end': {'latitude': -26.32, 'longitude': -48.82},
                },
                request_only=True,
            ),
            OpenApiExample(
                'Job pendente', value={'job_id': 1, 'status': 'pending'}, response_only=True, status_codes=['202']
            ),
            OpenApiExample(
                'Trajeto fictício calculado',
                value={
                    'id': 1,
                    'name': 'Trajeto fictício',
                    'route_group': 1,
                    'points': [{'latitude': -26.31, 'longitude': -48.81}],
                    'start_point': {'latitude': -26.3, 'longitude': -48.8},
                    'end_point': {'latitude': -26.32, 'longitude': -48.82},
                    'distance_meters': 3500.0,
                    'duration_seconds': 480.0,
                    'geometry': {'type': 'LineString', 'coordinates': [[-48.8, -26.3], [-48.82, -26.32]]},
                    'is_outdated': False,
                    'optimized_at': '2026-01-01T12:00:00-03:00',
                    'job_id': 1,
                    'status': 'done',
                    'order': [0, 1, 2],
                },
                response_only=True,
                status_codes=['200'],
            ),
        ],
    )
    @action(detail=True, methods=['post'])
    def optimize(self, request, pk=None):
        with transaction.atomic():
            path = self.get_object()
            path = Path.objects.select_for_update().select_related('route_group__company').get(pk=path.pk)
            self.check_object_permissions(request, path)
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            ids = serializer.validated_data.get('passenger_ids') or []
            stops = serializer.validated_data.get('stops') or []
            approved_count = Passenger.objects.filter(
                pk__in=ids, route_group=path.route_group, is_approved=True
            ).count()
            if ids and approved_count != len(ids):
                return Response({'detail': 'Há passageiros fora deste grupo ou sem aprovação.'}, status=400)
            if Travel.objects.filter(path=path, status=Travel.Status.IN_PROGRESS).exists():
                return Response({'detail': 'Não altere o trajeto durante a viagem.'}, status=400)
            path.is_outdated = True
            path.save(update_fields=['is_outdated'])
            start_data = dict(serializer.validated_data['start'])
            if stops:
                start_data['_stops'] = stops
            job = RouteOptimizationJob.objects.create(
                path=path,
                passenger_ids=ids,
                start=start_data,
                end=serializer.validated_data.get('end') or {},
            )

        if serializer.validated_data.get('async_mode'):
            return Response({'job_id': job.pk, 'status': job.status}, status=status.HTTP_202_ACCEPTED)

        try:
            job.status = RouteOptimizationJob.Status.RUNNING
            job.attempts = 1
            job.save(update_fields=['status', 'attempts', 'updated_at'])
            result = process_optimization(job)
        except GeocodingError as exc:
            job.status = RouteOptimizationJob.Status.FAILED
            job.error = str(exc)
            job.passenger_ids, job.start, job.end = [], {}, {}
            job.save(update_fields=['status', 'error', 'passenger_ids', 'start', 'end', 'updated_at'])
            return Response(
                {'detail': str(exc), 'job_id': job.pk, 'status': job.status},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OSRMError as exc:
            job.status = RouteOptimizationJob.Status.FAILED
            job.error = str(exc)
            job.passenger_ids, job.start, job.end = [], {}, {}
            job.save(update_fields=['status', 'error', 'passenger_ids', 'start', 'end', 'updated_at'])
            return Response(
                {'detail': str(exc), 'job_id': job.pk, 'status': job.status},
                status=getattr(exc, 'status_code', status.HTTP_503_SERVICE_UNAVAILABLE),
            )

        path.refresh_from_db()
        job.refresh_from_db()
        data = PathListAndRetrieveSerializer(path, context={'request': request}).data
        data['job_id'] = job.pk
        data['status'] = job.status
        if result is not None:
            data['order'] = result['order']
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Rotas/OSRM'],
        summary='Consulte a otimização',
        description=(
            'Somente empresa aprovada dona do trajeto; retorna o último job e se a rota precisa ser recalculada.'
        ),
        responses={
            200: inline_serializer(
                'RouteJobStatus',
                fields={
                    'job_id': serializers.IntegerField(),
                    'status': serializers.CharField(),
                    'error': serializers.CharField(),
                    'is_outdated': serializers.BooleanField(),
                },
            ),
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
            404: RESP_404_NOT_FOUND,
        },
    )
    @action(detail=True, methods=['get'])
    def optimization(self, request, pk=None):
        path = self.get_object()
        job = path.optimization_jobs.order_by('-pk').first()
        if not job:
            return Response({'detail': 'Nenhuma otimização solicitada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'job_id': job.pk, 'status': job.status, 'error': job.error, 'is_outdated': path.is_outdated})
