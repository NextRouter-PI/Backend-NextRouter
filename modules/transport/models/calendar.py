from datetime import datetime, timedelta
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.db.models.fields.json import KT
from django.utils import timezone

from .validation import related_values


def _combine_local(date, clock, days_before=0):
    return timezone.make_aware(datetime.combine(date - timedelta(days=days_before), clock))


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

    def window_for(self, date) -> tuple[datetime, datetime, datetime | None]:
        opens_at = _combine_local(date, self.opens_time, self.opens_days_before)
        normal_deadline = _combine_local(date, self.normal_time, self.normal_days_before)
        extension_deadline = (
            _combine_local(date, self.extension_time, self.extension_days_before)
            if self.extension_time is not None
            else None
        )
        return opens_at, normal_deadline, extension_deadline


class ServiceDayQuerySet(models.QuerySet):
    def for_company(self, company):
        return self.filter(route_group__company=company)

    def active(self):
        return self.filter(canceled_at__isnull=True)

    def future(self, *, today=None):
        return self.filter(date__gt=today or timezone.localdate())

    def due_for_closing(self, *, company_id=None, now=None):
        moment = now or timezone.now()
        qs = (
            self
            .active()
            .filter(normal_deadline__lte=moment)
            .annotate(
                closed_revision=KT('configuration_snapshot__closed_revision'),
                operational_issue=KT('configuration_snapshot__operational_issue'),
            )
            .filter(closed_revision__isnull=True, operational_issue__isnull=True)
        )
        if company_id is not None:
            qs = qs.filter(route_group__company_id=company_id)
        return qs.order_by('normal_deadline', 'pk')

    def visible_to(self, user):
        if not user or not user.is_authenticated or not user.is_active:
            return self.none()
        from modules.organizations.models import Company
        from modules.transport.models.travel import Travel

        owned_company = Company.objects.operational_for(user).filter(pk=OuterRef('route_group__company_id'))
        own_eligibility = ServiceDayEligibility.objects.visible_to(user).filter(day_id=OuterRef('pk'))
        visible_travel = Travel.objects.visible_to(user).filter(service_day_id=OuterRef('pk'))
        return self.filter(Exists(owned_company) | Exists(own_eligibility) | Exists(visible_travel))


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

    objects = ServiceDayQuerySet.as_manager()

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

    @property
    def is_canceled(self) -> bool:
        return self.canceled_at is not None

    def is_normal_window_open(self, *, now=None) -> bool:
        moment = now or timezone.now()
        return not self.is_canceled and self.opens_at <= moment < self.normal_deadline

    def is_extension_window_open(self, *, now=None) -> bool:
        moment = now or timezone.now()
        return (
            not self.is_canceled
            and self.extension_deadline is not None
            and self.normal_deadline <= moment < self.extension_deadline
        )

    def window_state(self, *, now=None) -> str:
        moment = now or timezone.now()
        if self.is_canceled:
            return 'canceled'
        if moment < self.opens_at:
            return 'not_open'
        if moment < self.normal_deadline:
            return 'normal'
        if self.extension_deadline and moment < self.extension_deadline:
            return 'extension'
        return 'closed'

    def has_started_execution(self) -> bool:
        return self.travels.filter(status__in=['in_progress', 'finished']).exists()

    def has_published_travels(self) -> bool:
        return self.travels.filter(published_revision__isnull=False).exists()

    def service_config(self, service_id: int) -> dict | None:
        return (self.configuration_snapshot or {}).get('services', {}).get(str(service_id))


class ServiceDayEligibilityQuerySet(models.QuerySet):
    def visible_to(self, user):
        if not user or not user.is_authenticated or not user.is_active:
            return self.none()
        from modules.organizations.models import Company, CompanyMembership

        owned_company = Company.objects.operational_for(user).filter(pk=OuterRef('day__route_group__company_id'))
        return self.filter(
            Exists(owned_company)
            | Q(
                passenger__user=user,
                group_membership__membership__status=CompanyMembership.Status.ACTIVE,
                day__route_group__company__is_approved=True,
                day__route_group__company__is_rejected=False,
                day__route_group__company__user__is_active=True,
            )
        )


class ServiceDayEligibility(models.Model):
    day = models.ForeignKey(ServiceDay, on_delete=models.PROTECT, related_name='eligibilities')
    passenger = models.ForeignKey('organizations.Passenger', on_delete=models.PROTECT, related_name='day_eligibilities')
    group_membership = models.ForeignKey(
        'organizations.PassengerGroupMembership', on_delete=models.PROTECT, related_name='day_eligibilities'
    )
    authorized_service_ids = models.JSONField(default=list, blank=True)
    point_snapshot = models.JSONField(default=dict, blank=True)

    objects = ServiceDayEligibilityQuerySet.as_manager()

    class Meta:
        verbose_name = 'Elegibilidade diária'
        verbose_name_plural = 'Elegibilidades diárias'
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['day', 'passenger'], name='day_passenger_eligibility_unique'),
        ]

    def __str__(self):
        return f'Elegibilidade #{self.pk}'

    def authorizes(self, service_id: int) -> bool:
        return service_id in (self.authorized_service_ids or [])

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
