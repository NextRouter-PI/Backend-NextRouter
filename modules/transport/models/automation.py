from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone


class AutomationScheduleQuerySet(models.QuerySet):
    def due_for_company(self, company_id, *, now=None):
        moment = now or timezone.now()
        return self.filter(route_group__company_id=company_id, enabled=True, next_run_at__lte=moment).order_by(
            'next_run_at', 'pk'
        )


class AutomationSchedule(models.Model):
    """Geração opt-in; números são escolhas explícitas, não políticas universais."""

    route_group = models.OneToOneField(
        'organizations.CompanyRouteGroup', on_delete=models.PROTECT, related_name='automation_schedule'
    )
    enabled = models.BooleanField(default=False)
    horizon_days = models.PositiveSmallIntegerField()
    batch_size = models.PositiveSmallIntegerField()
    interval_seconds = models.PositiveIntegerField()
    next_run_at = models.DateTimeField()
    cursor_date = models.DateField(null=True, blank=True)
    cycle_end_date = models.DateField(null=True, blank=True)
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    last_completed_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=32, blank=True)
    revision = models.PositiveIntegerField(default=1)
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='configured_automation_schedules'
    )
    configured_at = models.DateTimeField()

    objects = AutomationScheduleQuerySet.as_manager()

    class Meta:
        verbose_name = 'Agenda automática'
        verbose_name_plural = 'Agendas automáticas'
        indexes: ClassVar[list] = [models.Index(fields=['enabled', 'next_run_at'])]
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(horizon_days__gte=1, horizon_days__lte=31), name='automation_horizon_bounded'
            ),
            models.CheckConstraint(
                condition=models.Q(batch_size__gte=1, batch_size__lte=models.F('horizon_days')),
                name='automation_batch_bounded',
            ),
            models.CheckConstraint(condition=models.Q(interval_seconds__gte=1), name='automation_interval_positive'),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name='automation_revision_positive'),
            models.CheckConstraint(
                condition=models.Q(cursor_date__isnull=True, cycle_end_date__isnull=True)
                | models.Q(
                    cursor_date__isnull=False,
                    cycle_end_date__isnull=False,
                    cursor_date__lte=models.F('cycle_end_date'),
                ),
                name='automation_cursor_pair',
            ),
            models.CheckConstraint(
                condition=models.Q(last_error_code__in=['', 'generation_blocked']), name='automation_error_code_known'
            ),
        ]

    def __str__(self):
        return f'Agenda automática #{self.pk}'
