from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validation import related_values


class DailyResponse(models.Model):
    eligibility = models.OneToOneField(
        'router.ServiceDayEligibility', on_delete=models.PROTECT, related_name='response'
    )
    outbound_service = models.ForeignKey(
        'router.RecurringService', on_delete=models.PROTECT, null=True, blank=True, related_name='outbound_responses'
    )
    return_service = models.ForeignKey(
        'router.RecurringService', on_delete=models.PROTECT, null=True, blank=True, related_name='return_responses'
    )
    answered_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)
    outbound_withdrawn_at = models.DateTimeField(null=True, blank=True)
    return_withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Resposta diária'
        verbose_name_plural = 'Respostas diárias'
        constraints: ClassVar[list] = [
            models.CheckConstraint(condition=models.Q(revision__gte=1), name='daily_response_revision_positive'),
            models.CheckConstraint(
                condition=models.Q(outbound_withdrawn_at__isnull=True) | models.Q(outbound_service__isnull=False),
                name='response_outbound_withdrawal_choice',
            ),
            models.CheckConstraint(
                condition=models.Q(return_withdrawn_at__isnull=True) | models.Q(return_service__isnull=False),
                name='response_return_withdrawal_choice',
            ),
        ]

    def __str__(self):
        return f'Resposta #{self.pk}'

    def clean(self):
        super().clean()
        eligibility = related_values(self, 'eligibility', 'day__route_group_id', 'authorized_service_ids')
        errors = {}
        for field, direction in (('outbound_service', 'outbound'), ('return_service', 'return')):
            service = related_values(self, field, 'route_group_id', 'direction')
            if service and service['direction'] != direction:
                errors[field] = 'O sentido não corresponde ao trecho.'
            if service and eligibility:
                if service['route_group_id'] != eligibility['day__route_group_id']:
                    errors[field] = 'O serviço não pertence ao atendimento.'
                if getattr(self, f'{field}_id') not in eligibility['authorized_service_ids']:
                    errors[field] = 'O serviço não está autorizado para esse dia.'
        if errors:
            raise ValidationError(errors)


class DailyChangeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        APPROVED = 'approved', 'Aprovado'
        REJECTED = 'rejected', 'Recusado'
        WITHDRAWN = 'withdrawn', 'Retirado'
        EXPIRED = 'expired', 'Expirado'
        SUPERSEDED = 'superseded', 'Substituído'

    class Application(models.TextChoices):
        NOT_STARTED = 'not_started', 'Não iniciada'
        PREPARING = 'preparing', 'Preparando'
        FAILED = 'failed', 'Falhou'
        APPLIED = 'applied', 'Aplicada'

    response = models.ForeignKey(DailyResponse, on_delete=models.PROTECT, related_name='change_requests')
    leg = models.CharField(max_length=8, choices=[('outbound', 'Ida'), ('return', 'Retorno')])
    proposed_service = models.ForeignKey(
        'router.RecurringService', on_delete=models.PROTECT, related_name='change_requests'
    )
    expected_response_revision = models.PositiveIntegerField()
    previous_choice_snapshot = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='daily_requests')
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='daily_request_decisions',
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    application = models.CharField(max_length=12, choices=Application.choices, default=Application.NOT_STARTED)
    applied_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = 'Pedido de alteração diária'
        verbose_name_plural = 'Pedidos de alteração diária'
        constraints: ClassVar[list] = [
            models.CheckConstraint(condition=models.Q(leg__in=['outbound', 'return']), name='change_leg_valid'),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=['pending', 'approved', 'rejected', 'withdrawn', 'expired', 'superseded']
                ),
                name='change_status_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(application__in=['not_started', 'preparing', 'failed', 'applied']),
                name='change_application_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(expected_response_revision__gte=1), name='change_expected_revision'
            ),
            models.UniqueConstraint(
                fields=['response', 'leg'],
                condition=models.Q(status__in=['pending', 'approved']) & ~models.Q(application='applied'),
                name='change_one_open_request_per_leg',
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F('created_at')), name='change_expiry_order'
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(decided_at__isnull=True, decided_by__isnull=True)
                    | models.Q(decided_at__isnull=False, decided_by__isnull=False)
                ),
                name='change_decision_actor_pair',
            ),
            models.CheckConstraint(
                condition=~models.Q(status__in=['approved', 'rejected']) | models.Q(decided_at__isnull=False),
                name='change_decided_status_has_time',
            ),
            models.CheckConstraint(
                condition=~models.Q(status='pending') | models.Q(decided_at__isnull=True),
                name='change_pending_has_no_decision',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status__in=['withdrawn', 'expired', 'superseded'], closed_at__isnull=False)
                    | (~models.Q(status__in=['withdrawn', 'expired', 'superseded']) & models.Q(closed_at__isnull=True))
                ),
                name='change_terminal_has_close_time',
            ),
            models.CheckConstraint(
                condition=models.Q(decided_at__isnull=True)
                | models.Q(decided_at__gte=models.F('created_at'), decided_at__lt=models.F('expires_at')),
                name='change_decision_inside_window',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(application='applied', status='approved', applied_at__isnull=False)
                    | (~models.Q(application='applied') & models.Q(applied_at__isnull=True))
                ),
                name='change_applied_has_approval',
            ),
            models.CheckConstraint(
                condition=models.Q(applied_at__isnull=True) | models.Q(applied_at__gte=models.F('decided_at')),
                name='change_application_after_decision',
            ),
        ]

    def __str__(self):
        return f'Pedido diário #{self.pk}'

    def clean(self):
        super().clean()
        service = related_values(self, 'proposed_service', 'direction', 'route_group_id')
        response = related_values(
            self, 'response', 'eligibility__day__route_group_id', 'eligibility__authorized_service_ids'
        )
        errors = {}
        if service and service['direction'] != self.leg:
            errors['proposed_service'] = 'O serviço proposto não corresponde ao trecho.'
        if (
            response
            and service
            and (
                service['route_group_id'] != response['eligibility__day__route_group_id']
                or self.proposed_service_id not in response['eligibility__authorized_service_ids']
            )
        ):
            errors['proposed_service'] = 'O serviço proposto não está autorizado nesse atendimento.'
        if errors:
            raise ValidationError(errors)
