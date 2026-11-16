from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .validation import related_values


class ResponsePolicy(models.Model):
    route_group = models.OneToOneField(
        'organizations.CompanyRouteGroup', on_delete=models.PROTECT, related_name='response_policy'
    )
    opens_days_before = models.PositiveSmallIntegerField()
    opens_time = models.TimeField()
    normal_days_before = models.PositiveSmallIntegerField()
    normal_time = models.TimeField()
    extension_days_before = models.PositiveSmallIntegerField(null=True, blank=True)
    extension_time = models.TimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Política de respostas'
        verbose_name_plural = 'Políticas de respostas'
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=(
                    models.Q(opens_days_before__gt=models.F('normal_days_before'))
                    | models.Q(opens_days_before=models.F('normal_days_before'), opens_time__lt=models.F('normal_time'))
                ),
                name='policy_open_before_normal',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(extension_days_before__isnull=True, extension_time__isnull=True)
                    | (
                        models.Q(extension_days_before__isnull=False, extension_time__isnull=False)
                        & (
                            models.Q(extension_days_before__lt=models.F('normal_days_before'))
                            | models.Q(
                                extension_days_before=models.F('normal_days_before'),
                                extension_time__gt=models.F('normal_time'),
                            )
                        )
                    )
                ),
                name='policy_extension_after_normal',
            ),
        ]

    def __str__(self):
        return f'Política #{self.pk}'


class ServiceDay(models.Model):
    route_group = models.ForeignKey('organizations.CompanyRouteGroup', on_delete=models.PROTECT, related_name='days')
    date = models.DateField()
    opens_at = models.DateTimeField()
    normal_deadline = models.DateTimeField()
    extension_deadline = models.DateTimeField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)
    configuration_snapshot = models.JSONField(default=dict, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='canceled_service_days'
    )
    cancellation_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = 'Dia de atendimento'
        verbose_name_plural = 'Dias de atendimento'
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['route_group', 'date'], name='service_day_group_date_unique'),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name='service_day_revision_positive'),
            models.CheckConstraint(
                condition=models.Q(opens_at__lt=models.F('normal_deadline')), name='day_deadlines_order'
            ),
            models.CheckConstraint(
                condition=models.Q(extension_deadline__isnull=True)
                | models.Q(extension_deadline__gt=models.F('normal_deadline')),
                name='day_extension_after_normal',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(canceled_at__isnull=True, canceled_by__isnull=True, cancellation_reason='')
                    | (
                        models.Q(canceled_at__isnull=False, canceled_by__isnull=False)
                        & ~models.Q(cancellation_reason='')
                    )
                ),
                name='day_cancellation_has_audit',
            ),
        ]

    def __str__(self):
        return f'Atendimento #{self.pk}'


class ServiceDayEligibility(models.Model):
    day = models.ForeignKey(ServiceDay, on_delete=models.PROTECT, related_name='eligibilities')
    passenger = models.ForeignKey('organizations.Passenger', on_delete=models.PROTECT, related_name='day_eligibilities')
    group_membership = models.ForeignKey(
        'organizations.PassengerGroupMembership', on_delete=models.PROTECT, related_name='day_eligibilities'
    )
    authorized_service_ids = models.JSONField(default=list, blank=True)
    point_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Elegibilidade diária'
        verbose_name_plural = 'Elegibilidades diárias'
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['day', 'passenger'], name='day_passenger_eligibility_unique'),
        ]

    def __str__(self):
        return f'Elegibilidade #{self.pk}'

    def clean(self):
        super().clean()
        errors = {}
        day = related_values(self, 'day', 'route_group_id')
        participation = related_values(self, 'group_membership', 'route_group_id', 'membership__passenger_id')
        if participation and participation['membership__passenger_id'] != self.passenger_id:
            errors['passenger'] = 'A elegibilidade deve corresponder ao passageiro da participação.'
        if day and participation and day['route_group_id'] != participation['route_group_id']:
            errors['group_membership'] = 'A participação deve corresponder ao grupo atendido.'
        ids = self.authorized_service_ids
        if not isinstance(ids, list) or any(type(value) is not int or value < 1 for value in ids):
            errors['authorized_service_ids'] = 'Informe uma lista de IDs de serviços positivos.'
        elif len(ids) != len(set(ids)):
            errors['authorized_service_ids'] = 'Não repita serviços na elegibilidade.'
        if errors:
            raise ValidationError(errors)
