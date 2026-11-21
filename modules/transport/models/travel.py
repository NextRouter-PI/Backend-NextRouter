from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.utils.translation import gettext_lazy as _

from modules.organizations.models.company import Company
from modules.organizations.models.driver import Driver
from modules.transport.models.vehicle import Vehicle
from shared.exceptions import require


class TravelQuerySet(models.QuerySet):
    def dated(self):
        return self.filter(service_day__isnull=False)

    def for_company(self, company):
        return self.filter(company=company)

    def scheduled(self):
        return self.filter(status=Travel.Status.SCHEDULED)

    def active(self):
        return self.filter(status=Travel.Status.IN_PROGRESS)

    def not_canceled(self):
        return self.exclude(status=Travel.Status.CANCELED)

    def with_execution_details(self):
        return self.select_related('company', 'service_day', 'service', 'driver__user', 'vehicle')

    def conflicting_resources(self, *, driver_id=None, vehicle_id=None, exclude_pk=None):
        query = Q()
        if driver_id is not None:
            query |= Q(driver_id=driver_id)
        if vehicle_id is not None:
            query |= Q(vehicle_id=vehicle_id)
        if not query:
            return self.none()
        qs = self.filter(query)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs

    def overlapping_window(self, *, start, end, driver_id=None, vehicle_id=None, exclude_pk=None):
        return (
            self
            .dated()
            .not_canceled()
            .conflicting_resources(driver_id=driver_id, vehicle_id=vehicle_id, exclude_pk=exclude_pk)
            .filter(planned_start__lt=end, planned_end__gt=start)
        )

    def _operational_filter(self, user):
        from modules.organizations.models import CompanyMembership

        owned_company = Company.objects.operational_for(user).filter(pk=OuterRef('company_id'))
        driver_member = CompanyMembership.objects.active().filter(
            company_id=OuterRef('company_id'),
            company__is_approved=True,
            company__is_rejected=False,
            company__user__is_active=True,
            driver__user=user,
        )
        return Exists(owned_company) | (Q(driver__user=user) & Exists(driver_member))

    def visible_to(self, user):
        if not user or not user.is_authenticated or not user.is_active:
            return self.none()
        from modules.organizations.models import CompanyMembership
        from modules.transport.models.participation import TravelParticipation

        passenger_participation = TravelParticipation.objects.filter(
            travel_id=OuterRef('pk'),
            eligibility__passenger__user=user,
            eligibility__group_membership__membership__status=CompanyMembership.Status.ACTIVE,
            eligibility__day__route_group__company__is_approved=True,
            eligibility__day__route_group__company__is_rejected=False,
            eligibility__day__route_group__company__user__is_active=True,
        )
        return self.dated().filter(self._operational_filter(user) | Exists(passenger_participation))

    def operational_for(self, user):
        if not user or not user.is_authenticated or not user.is_active:
            return self.none()
        return self.dated().filter(self._operational_filter(user))


class Travel(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', _('Agendada')
        IN_PROGRESS = 'in_progress', _('Em andamento')
        FINISHED = 'finished', _('Finalizada')
        CANCELED = 'canceled', _('Cancelada')

    class PlanningStatus(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        PREPARING = 'preparing', 'Preparando'
        BLOCKED = 'blocked', 'Com pendência'
        READY = 'ready', 'Pronto'

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
        choices=PlanningStatus.choices,
        default=PlanningStatus.DRAFT,
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

    objects = TravelQuerySet.as_manager()

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
        company = self._state.fields_cache.get('company')
        if company is not None and 'user' in company._state.fields_cache:
            return f'Viagem do dia {day} da empresa {company.user.name.title()}'
        return f'Viagem #{self.pk} (dia {day})'

    @property
    def is_editable(self) -> bool:
        return self.status == self.Status.SCHEDULED and not self.service_day.canceled_at

    @property
    def is_published_current(self) -> bool:
        return (
            self.published_revision is not None
            and self.published_revision == self.revision
            and self.published_snapshot_id is not None
            and self.published_snapshot_id == self.current_snapshot_id
        )

    def ensure_editable(self) -> None:
        require(self.status == self.Status.SCHEDULED, 'travel_not_scheduled', 'A viagem não pode mais ser alterada.')
        require(not self.service_day.canceled_at, 'day_canceled', 'O atendimento está cancelado.')

    def frozen_service(self) -> dict:
        config = self.service_day.service_config(self.service_id)
        require(config is not None, 'missing_configuration', 'O serviço não está congelado no dia.')
        return config

    def invalidate(self) -> None:
        self.ensure_editable()
        self.revision = max([self.revision, *self.route_snapshots.values_list('revision', flat=True)]) + 1
        self.current_snapshot = None
        self.planning_status = self.PlanningStatus.DRAFT
        self.save(update_fields=['revision', 'current_snapshot', 'planning_status'])

    def recompute_planning_status(self) -> str:
        from modules.transport.models.planning import RouteSnapshot

        if self.current_snapshot_id and self.current_snapshot.state == RouteSnapshot.State.READY:
            new_status = self.PlanningStatus.READY
        elif self.route_snapshots.filter(
            change_request__isnull=True,
            base_revision=self.revision,
            state=RouteSnapshot.State.PENDING,
        ).exists():
            new_status = self.PlanningStatus.PREPARING
        else:
            new_status = self.PlanningStatus.DRAFT
        if self.planning_status != new_status:
            self.planning_status = new_status
            self.save(update_fields=['planning_status'])
        return new_status

    def restore_previous_planning_status(self) -> None:
        if self.status != self.Status.SCHEDULED:
            return
        snapshot = self.current_snapshot
        pending = self.route_snapshots.filter(
            change_request__status='approved', change_request__application='preparing'
        ).exists()
        self.planning_status = (
            self.PlanningStatus.PREPARING
            if pending
            else self.PlanningStatus.READY
            if snapshot and snapshot.state == 'ready' and snapshot.revision == self.revision
            else self.PlanningStatus.BLOCKED
        )
        self.save(update_fields=['planning_status'])

    def occupied_seat_count(self, *, exclude_request_id=None) -> int:
        allocated = self.participations.active_occupancy().count()
        reservations = self.seat_reservations.held()
        if exclude_request_id is not None:
            reservations = reservations.exclude(request_id=exclude_request_id)
        return allocated + reservations.count()

    def recipient_user_ids(self) -> list:
        recipients = [self.company.user_id]
        if self.driver_id:
            recipients.append(self.driver.user_id)
        recipients.extend(self.participations.values_list('eligibility__passenger__user_id', flat=True))
        return recipients

    def mark_started(self, *, now) -> None:
        self.status = self.Status.IN_PROGRESS
        self.started_at = now
        self.full_clean()
        self.save(update_fields=['status', 'started_at'])

    def mark_finished(self, *, now) -> None:
        self.status = self.Status.FINISHED
        self.finished_at = now
        self.current_latitude = None
        self.current_longitude = None
        self.location_updated_at = None
        self.save(
            update_fields=['status', 'finished_at', 'current_latitude', 'current_longitude', 'location_updated_at']
        )

    def mark_canceled(self) -> None:
        self.status = self.Status.CANCELED
        self.save(update_fields=['status'])

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
