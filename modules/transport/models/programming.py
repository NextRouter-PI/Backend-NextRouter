from datetime import timedelta
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .validation import related_values, same_company


class RecurringServiceQuerySet(models.QuerySet):
    def for_group(self, group):
        return self.filter(route_group=group)

    def valid_on(self, date):
        return self.filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=date),
            Q(valid_until__isnull=True) | Q(valid_until__gte=date),
        )

    def with_snapshot_relations(self):
        return self.select_related(
            'origin',
            'destination',
            'vehicle__garage_point',
            'driver_membership',
        ).prefetch_related('configured_stops__point')


class RecurringService(models.Model):
    class Direction(models.TextChoices):
        OUTBOUND = 'outbound', 'Ida'
        RETURN = 'return', 'Retorno'

    route_group = models.ForeignKey(
        'organizations.CompanyRouteGroup', on_delete=models.PROTECT, related_name='services'
    )
    name = models.CharField(max_length=100)
    direction = models.CharField(max_length=8, choices=Direction.choices)
    is_shared = models.BooleanField(default=False, db_index=True, verbose_name='Serviço compartilhado')
    weekdays = models.PositiveSmallIntegerField(help_text='Máscara: segunda=1, terça=2, ... domingo=64.')
    target_time = models.TimeField(help_text='Chegada desejada na ida; partida no retorno.')
    planned_duration = models.DurationField(null=True, blank=True)
    turnaround_duration = models.DurationField(null=True, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    driver_membership = models.ForeignKey(
        'organizations.CompanyMembership',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='habitual_services',
    )
    vehicle = models.ForeignKey(
        'router.Vehicle', on_delete=models.PROTECT, null=True, blank=True, related_name='services'
    )
    origin = models.ForeignKey(
        'organizations.OperationalPoint',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='origin_services',
    )
    destination = models.ForeignKey(
        'organizations.OperationalPoint',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='destination_services',
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_services')

    objects = RecurringServiceQuerySet.as_manager()

    class Meta:
        verbose_name = 'Serviço habitual'
        verbose_name_plural = 'Serviços habituais'
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(planned_duration__isnull=True) | models.Q(planned_duration__gt=timedelta()),
                name='service_planned_duration_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(turnaround_duration__isnull=True) | models.Q(turnaround_duration__gte=timedelta()),
                name='service_turnaround_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(direction__in=['outbound', 'return']), name='service_direction_valid'
            ),
            models.CheckConstraint(
                condition=models.Q(weekdays__gte=1, weekdays__lte=127), name='service_weekdays_valid'
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(valid_from__isnull=True)
                    | models.Q(valid_until__isnull=True)
                    | models.Q(valid_until__gte=models.F('valid_from'))
                ),
                name='service_validity_order',
            ),
        ]

    def __str__(self):
        return f'Serviço #{self.pk}'

    def runs_on(self, date) -> bool:
        if self.valid_from and date < self.valid_from:
            return False
        if self.valid_until and date > self.valid_until:
            return False
        return bool(self.weekdays & (1 << date.weekday()))

    def effective_origin(self):
        return self.origin or (self.vehicle.garage_point if self.vehicle_id else None)

    def effective_destination(self, group):
        if self.destination is not None:
            return self.destination
        if self.direction == self.Direction.OUTBOUND:
            return group.destination
        return self.vehicle.garage_point if self.vehicle_id else None

    def clean(self):
        super().clean()
        errors = {}
        group = related_values(self, 'route_group', 'company_id')
        company_id = group['company_id'] if group else None
        for field in ('origin', 'destination', 'vehicle'):
            same_company(errors, field, related_values(self, field, 'company_id'), company_id)
        driver = related_values(self, 'driver_membership', 'company_id', 'driver_id', 'status')
        same_company(errors, 'driver_membership', driver, company_id)
        if driver and (driver['driver_id'] is None or driver['status'] != 'active'):
            errors['driver_membership'] = 'Selecione um vínculo ativo de motorista.'
        if errors:
            raise ValidationError(errors)


class PassengerServiceAuthorization(models.Model):
    participation = models.ForeignKey(
        'organizations.PassengerGroupMembership', on_delete=models.PROTECT, related_name='service_authorizations'
    )
    service = models.ForeignKey(RecurringService, on_delete=models.PROTECT, related_name='authorizations')
    direction = models.CharField(max_length=8, choices=RecurringService.Direction.choices)
    is_habitual = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Autorização de serviço'
        verbose_name_plural = 'Autorizações de serviços'
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['participation', 'service'], name='authorization_unique_service'),
            models.UniqueConstraint(
                fields=['participation'],
                condition=models.Q(is_habitual=True),
                name='authorization_one_habitual_outbound',
            ),
            models.CheckConstraint(
                condition=models.Q(direction__in=['outbound', 'return']), name='authorization_direction_valid'
            ),
            models.CheckConstraint(
                condition=models.Q(is_habitual=False) | models.Q(direction='outbound'),
                name='authorization_habitual_outbound',
            ),
        ]

    def __str__(self):
        return f'Autorização #{self.pk}'

    def clean(self):
        super().clean()
        service = related_values(self, 'service', 'route_group_id', 'direction')
        participation = related_values(self, 'participation', 'route_group_id', 'ended_at')
        errors = {}
        if service and service['direction'] != self.direction:
            errors['direction'] = 'O sentido deve corresponder ao serviço.'
        if service and participation and service['route_group_id'] != participation['route_group_id']:
            errors['service'] = 'O serviço deve pertencer ao grupo da participação.'
        if errors:
            raise ValidationError(errors)


class RecurringServiceStop(models.Model):
    service = models.ForeignKey(RecurringService, on_delete=models.PROTECT, related_name='configured_stops')
    point = models.ForeignKey('organizations.OperationalPoint', on_delete=models.PROTECT, related_name='service_stops')
    position = models.PositiveIntegerField()

    class Meta:
        verbose_name = 'Parada habitual'
        verbose_name_plural = 'Paradas habituais'
        ordering = ('service_id', 'position')
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['service', 'position'], name='service_stop_position_unique'),
            models.UniqueConstraint(fields=['service', 'point'], name='service_stop_point_unique'),
            models.CheckConstraint(condition=models.Q(position__gte=1), name='service_stop_position_positive'),
        ]

    def __str__(self):
        return f'Parada habitual #{self.pk}'

    def clean(self):
        super().clean()
        service = related_values(self, 'service', 'route_group__company_id')
        point = related_values(self, 'point', 'company_id')
        if service and point and service['route_group__company_id'] != point['company_id']:
            raise ValidationError({'point': 'A parada deve pertencer à empresa do serviço.'})
