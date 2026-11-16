from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.organizations.models.company import Company
from modules.organizations.models.driver import Driver
from modules.transport.models.vehicle import Vehicle


class Travel(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', _('Agendada')
        IN_PROGRESS = 'in_progress', _('Em andamento')
        FINISHED = 'finished', _('Finalizada')
        CANCELED = 'canceled', _('Cancelada')

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        verbose_name=_('Empresa'),
        related_name='travels',
    )

    service_day = models.ForeignKey('router.ServiceDay', on_delete=models.PROTECT, related_name='travels')
    service = models.ForeignKey('router.RecurringService', on_delete=models.PROTECT, related_name='travels')
    planned_start = models.DateTimeField()
    planned_end = models.DateTimeField()
    revision = models.PositiveIntegerField(default=1)
    planning_status = models.CharField(
        max_length=10,
        choices=[('draft', 'Rascunho'), ('preparing', 'Preparando'), ('blocked', 'Com pendência'), ('ready', 'Pronto')],
        default='draft',
    )
    published_revision = models.PositiveIntegerField(null=True, blank=True)
    current_snapshot = models.ForeignKey(
        'router.RouteSnapshot', on_delete=models.PROTECT, null=True, blank=True, related_name='current_for_travels'
    )
    published_snapshot = models.ForeignKey(
        'router.RouteSnapshot', on_delete=models.PROTECT, null=True, blank=True, related_name='published_for_travels'
    )

    driver = models.ForeignKey(
        Driver,
        on_delete=models.PROTECT,
        verbose_name=_('Motorista'),
        related_name='travels',
        null=True,
        blank=True,
    )

    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, null=True, blank=True, related_name='travels')

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        verbose_name=_('Status'),
        db_index=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Data de início'),
        db_index=True,
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Data de término'),
    )

    # Última localização conhecida do motorista durante a viagem, atualizada via WebSocket.
    # Usa campos float simples (não GeoDjango/PointField) para não depender de GDAL/PostGIS.
    current_latitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Latitude atual'),
    )

    current_longitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Longitude atual'),
    )

    location_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Última atualização de localização'),
    )

    class Meta:
        verbose_name = _('Viagem')
        verbose_name_plural = _('Viagens')
        db_table = 'router_travel'
        ordering = ('-started_at',)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(published_snapshot__isnull=True, published_revision__isnull=True)
                | models.Q(published_snapshot__isnull=False, published_revision__isnull=False),
                name='travel_publication_pointer_pair',
            ),
            models.CheckConstraint(
                condition=~models.Q(planning_status='ready') | models.Q(current_snapshot__isnull=False),
                name='dated_travel_ready_has_snapshot',
            ),
            models.CheckConstraint(
                condition=~models.Q(status='in_progress') | models.Q(current_snapshot=models.F('published_snapshot')),
                name='dated_travel_start_published_snapshot',
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=['scheduled', 'in_progress', 'finished', 'canceled']),
                name='dated_travel_execution_state_valid',
            ),
            models.CheckConstraint(
                condition=~models.Q(status='finished')
                | models.Q(finished_at__isnull=False, finished_at__gte=models.F('started_at')),
                name='dated_travel_finish_after_start',
            ),
            models.CheckConstraint(
                condition=~models.Q(planning_status='ready') | models.Q(driver__isnull=False, vehicle__isnull=False),
                name='dated_travel_ready_designation',
            ),
            models.UniqueConstraint(fields=['service_day', 'service'], name='travel_one_per_service_day'),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name='travel_revision_positive'),
            models.CheckConstraint(
                condition=models.Q(planning_status__in=['draft', 'preparing', 'blocked', 'ready']),
                name='travel_planning_state_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(published_revision__isnull=True)
                | models.Q(published_revision__gte=1, published_revision__lte=models.F('revision')),
                name='travel_publication_revision_order',
            ),
            models.CheckConstraint(
                condition=models.Q(
                    planned_start__isnull=False, planned_end__isnull=False, planned_end__gt=models.F('planned_start')
                ),
                name='dated_travel_planned_period',
            ),
            models.CheckConstraint(
                condition=~models.Q(status__in=['in_progress', 'finished'])
                | models.Q(driver__isnull=False, vehicle__isnull=False, started_at__isnull=False),
                name='dated_travel_execution_designation',
            ),
            models.CheckConstraint(
                condition=~models.Q(status='in_progress')
                | models.Q(
                    planning_status='ready', published_revision__isnull=False, published_revision=models.F('revision')
                ),
                name='dated_travel_start_current_revision',
            ),
            models.UniqueConstraint(
                fields=['driver'], condition=models.Q(status='in_progress'), name='one_active_travel_per_driver'
            ),
            models.UniqueConstraint(
                fields=['vehicle'], condition=models.Q(status='in_progress'), name='one_active_travel_per_vehicle'
            ),
        )

    def __str__(self):
        day = self.started_at.day if self.started_at else '?'
        return f'Viagem do dia {day} da empresa {self.company.user.name.title()}'

    def clean(self):
        super().clean()
        from .validation import related_values, same_company

        errors = {}
        day = related_values(self, 'service_day', 'route_group_id', 'route_group__company_id')
        service = related_values(self, 'service', 'route_group_id')
        if day and day['route_group__company_id'] != self.company_id:
            errors['service_day'] = 'O atendimento deve pertencer à empresa da viagem.'
        if day and service and day['route_group_id'] != service['route_group_id']:
            errors['service'] = 'O serviço deve pertencer ao grupo do atendimento.'
        same_company(errors, 'vehicle', related_values(self, 'vehicle', 'company_id'), self.company_id)
        for field, revision in (('current_snapshot', self.revision), ('published_snapshot', self.published_revision)):
            snapshot = related_values(self, field, 'travel_id', 'revision', 'state')
            if snapshot and (snapshot['travel_id'] != self.pk or snapshot['revision'] != revision):
                errors[field] = 'O percurso deve corresponder à viagem e à revisão informadas.'
            if (
                snapshot
                and field == 'current_snapshot'
                and self.planning_status == 'ready'
                and snapshot['state'] != 'ready'
            ):
                errors[field] = 'O percurso atual ainda não está pronto.'
            if snapshot and field == 'published_snapshot' and snapshot['state'] != 'ready':
                errors[field] = 'O percurso publicado precisa ter resultado pronto.'
        if self.driver_id:
            from modules.organizations.models import CompanyMembership

            statuses = ['active'] if self.status == self.Status.SCHEDULED else ['active', 'ended']
            if not CompanyMembership.objects.filter(
                company_id=self.company_id, driver_id=self.driver_id, status__in=statuses
            ).exists():
                errors['driver'] = 'O motorista não possui vínculo empresarial compatível.'
        if errors:
            raise ValidationError(errors)
