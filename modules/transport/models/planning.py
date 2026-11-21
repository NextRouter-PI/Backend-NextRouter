from math import isfinite
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from shared.exceptions import require
from shared.geo import valid_coordinate_pair

from .validation import related_values


class RouteSnapshot(models.Model):
    class State(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        READY = 'ready', 'Pronto'
        FAILED = 'failed', 'Falhou'
        SUPERSEDED = 'superseded', 'Obsoleto'

    travel = models.ForeignKey('router.Travel', on_delete=models.PROTECT, related_name='route_snapshots')
    revision = models.PositiveIntegerField()
    base_revision = models.PositiveIntegerField()
    change_request = models.ForeignKey(
        'router.DailyChangeRequest', on_delete=models.PROTECT, null=True, blank=True, related_name='route_snapshots'
    )
    state = models.CharField(
        max_length=10,
        choices=State.choices,
        default=State.PENDING,
    )
    input_data = models.JSONField(default=dict, blank=True)
    origin = models.JSONField(default=dict, blank=True)
    destination = models.JSONField(default=dict, blank=True)
    geometry = models.JSONField(null=True, blank=True)
    distance_meters = models.FloatField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    calculated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Snapshot de percurso'
        verbose_name_plural = 'Snapshots de percurso'
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(planned_start__isnull=True, planned_end__isnull=True)
                | models.Q(
                    planned_start__isnull=False, planned_end__isnull=False, planned_end__gt=models.F('planned_start')
                ),
                name='snapshot_planned_period_pair',
            ),
            models.UniqueConstraint(fields=['travel', 'revision'], name='snapshot_travel_revision_unique'),
            models.CheckConstraint(
                condition=models.Q(base_revision__gte=1, revision__gte=models.F('base_revision')),
                name='snapshot_revision_order',
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=['pending', 'ready', 'failed', 'superseded']), name='snapshot_state_valid'
            ),
            models.CheckConstraint(
                condition=models.Q(distance_meters__isnull=True) | models.Q(distance_meters__gte=0),
                name='snapshot_distance_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(duration_seconds__isnull=True) | models.Q(duration_seconds__gte=0),
                name='snapshot_duration_nonnegative',
            ),
            models.CheckConstraint(
                condition=~models.Q(state='ready')
                | models.Q(
                    geometry__isnull=False,
                    distance_meters__isnull=False,
                    duration_seconds__isnull=False,
                    calculated_at__isnull=False,
                ),
                name='snapshot_ready_has_result',
            ),
            models.CheckConstraint(
                condition=models.Q(calculated_at__isnull=True) | models.Q(calculated_at__gte=models.F('created_at')),
                name='snapshot_calculated_after_creation',
            ),
        ]

    def __str__(self):
        return f'Percurso #{self.pk} — revisão {self.revision}'

    @property
    def is_ready(self) -> bool:
        return self.state == self.State.READY

    def mark_failed(self) -> None:
        self.state = self.State.FAILED
        self.save(update_fields=['state'])

    def mark_superseded(self) -> None:
        self.state = self.State.SUPERSEDED
        self.save(update_fields=['state'])

    def clean(self):
        super().clean()
        errors = {}
        travel = related_values(self, 'travel', 'service_day_id')
        if travel and travel['service_day_id'] is None:
            errors['travel'] = 'Snapshots novos exigem viagem datada.'
        for field in ('input_data', 'origin', 'destination'):
            if not isinstance(getattr(self, field), dict):
                errors[field] = 'Informe um objeto de snapshot.'
        if self.state == 'ready':
            geometry = self.geometry
            if not (
                isinstance(geometry, dict)
                and geometry.get('type') == 'LineString'
                and isinstance(geometry.get('coordinates'), list)
                and len(geometry['coordinates']) >= 2
                and all(valid_coordinate_pair(point) for point in geometry['coordinates'])
            ):
                errors['geometry'] = 'Informe uma geometria LineString válida.'
            for field in ('origin', 'destination'):
                point = getattr(self, field)
                if not isinstance(point, dict) or not valid_coordinate_pair([
                    point.get('longitude'),
                    point.get('latitude'),
                ]):
                    errors[field] = 'Informe um ponto operacional congelado válido.'
        for field in ('distance_meters', 'duration_seconds'):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, (int, float)) or not isfinite(value) or value < 0):
                errors[field] = 'Informe uma medida finita não negativa.'
        if errors:
            raise ValidationError(errors)


class RouteStop(models.Model):
    class State(models.TextChoices):
        WAITING = 'waiting', 'Pendente'
        COMPLETED = 'completed', 'Atendida'
        SKIPPED = 'skipped', 'Ignorada'

    snapshot = models.ForeignKey(RouteSnapshot, on_delete=models.PROTECT, related_name='stops')
    position = models.PositiveIntegerField()
    point_snapshot = models.JSONField()
    state = models.CharField(
        max_length=10,
        choices=State.choices,
        default=State.WAITING,
    )
    arrived_at = models.DateTimeField(null=True, blank=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='handled_route_stops'
    )

    class Meta:
        verbose_name = 'Parada de viagem'
        verbose_name_plural = 'Paradas de viagem'
        ordering = ('snapshot_id', 'position')
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['snapshot', 'position'], name='route_stop_position_unique'),
            models.CheckConstraint(condition=models.Q(position__gte=1), name='route_stop_position_positive'),
            models.CheckConstraint(
                condition=models.Q(state='waiting', handled_at__isnull=True, handled_by__isnull=True)
                | models.Q(state__in=['completed', 'skipped'], handled_at__isnull=False, handled_by__isnull=False),
                name='route_stop_handling_audit',
            ),
            models.CheckConstraint(
                condition=models.Q(arrived_at__isnull=True)
                | models.Q(handled_at__isnull=True)
                | models.Q(handled_at__gte=models.F('arrived_at')),
                name='route_stop_handled_after_arrival',
            ),
        ]

    def __str__(self):
        return f'Parada #{self.pk}'

    def ensure_can_handle(self, *, skipped: bool = False) -> bool:
        """Valida ordem sequencial e presenças pendentes; retorna False se já estiver no estado alvo."""
        from modules.transport.models.participation import TravelParticipation

        target = self.State.SKIPPED if skipped else self.State.COMPLETED
        if self.state != self.State.WAITING:
            require(self.state == target, 'invalid_transition', 'A parada já foi tratada.')
            return False
        require(
            not self.snapshot.stops.filter(position__lt=self.position, state=self.State.WAITING).exists(),
            'stop_out_of_order',
            'Trate a parada anterior primeiro.',
        )
        p_status = TravelParticipation.Status
        for item in self.participants.select_related('participation'):
            status = item.participation.status
            permitted = (
                (p_status.WITHDRAWN, p_status.NO_SHOW, p_status.DROPPED_OFF)
                if skipped
                else (
                    (p_status.ON_BOARD, p_status.DROPPED_OFF, p_status.NO_SHOW, p_status.WITHDRAWN)
                    if item.operation == RouteStopParticipant.Operation.BOARD
                    else (p_status.DROPPED_OFF, p_status.WITHDRAWN, p_status.NO_SHOW)
                )
            )
            require(
                status in permitted,
                'pending_participants',
                'Registre os eventos individuais antes de tratar a parada.',
            )
        return True

    def mark_handled(self, *, actor_id, now, skipped: bool = False) -> None:
        self.state = self.State.SKIPPED if skipped else self.State.COMPLETED
        self.handled_by_id = actor_id
        self.handled_at = now
        self.save(update_fields=['state', 'handled_by', 'handled_at'])

    def clean(self):
        super().clean()
        point = self.point_snapshot
        if not isinstance(point, dict) or not valid_coordinate_pair([point.get('longitude'), point.get('latitude')]):
            raise ValidationError({'point_snapshot': 'Informe coordenadas congeladas válidas.'})


class RouteStopParticipant(models.Model):
    class Operation(models.TextChoices):
        BOARD = 'board', 'Embarque'
        DROP = 'drop', 'Desembarque'

    stop = models.ForeignKey(RouteStop, on_delete=models.PROTECT, related_name='participants')
    participation = models.ForeignKey(
        'router.TravelParticipation', on_delete=models.PROTECT, related_name='route_stops'
    )
    operation = models.CharField(max_length=5, choices=Operation.choices)

    class Meta:
        verbose_name = 'Atendimento na parada'
        verbose_name_plural = 'Atendimentos nas paradas'
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=['stop', 'participation', 'operation'], name='stop_participant_operation_unique'
            ),
            models.CheckConstraint(condition=models.Q(operation__in=['board', 'drop']), name='stop_operation_valid'),
        ]

    def __str__(self):
        return f'Atendimento na parada #{self.pk}'

    def clean(self):
        super().clean()
        stop = related_values(self, 'stop', 'snapshot__travel_id')
        participation = related_values(self, 'participation', 'travel_id')
        if stop and participation and stop['snapshot__travel_id'] != participation['travel_id']:
            raise ValidationError({'participation': 'A participação deve pertencer à viagem do percurso.'})


class TravelPublication(models.Model):
    travel = models.ForeignKey('router.Travel', on_delete=models.PROTECT, related_name='publications')
    snapshot = models.OneToOneField(RouteSnapshot, on_delete=models.PROTECT, related_name='publication')
    revision = models.PositiveIntegerField()
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='travel_publications'
    )
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Publicação de viagem'
        verbose_name_plural = 'Publicações de viagens'
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['travel', 'revision'], name='publication_travel_revision_unique'),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name='publication_revision_positive'),
        ]

    def __str__(self):
        return f'Publicação #{self.pk}'

    def clean(self):
        super().clean()
        snapshot = related_values(self, 'snapshot', 'travel_id', 'revision', 'state')
        if snapshot and (
            snapshot['travel_id'] != self.travel_id
            or snapshot['revision'] != self.revision
            or snapshot['state'] != 'ready'
        ):
            raise ValidationError({'snapshot': 'Publique um percurso pronto da viagem/revisão informadas.'})
