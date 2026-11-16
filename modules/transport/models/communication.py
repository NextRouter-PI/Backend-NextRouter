from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .validation import related_values


class DriverInvitation(models.Model):
    travel = models.ForeignKey('router.Travel', on_delete=models.PROTECT, related_name='driver_invitations')
    driver_membership = models.ForeignKey(
        'organizations.CompanyMembership', on_delete=models.PROTECT, related_name='travel_invitations'
    )
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sent_invitations')
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_current = models.BooleanField(default=True)
    status = models.CharField(
        max_length=8,
        choices=[
            ('pending', 'Pendente'),
            ('accepted', 'Aceito'),
            ('declined', 'Recusado'),
            ('expired', 'Expirado'),
            ('revoked', 'Revogado'),
        ],
        default='pending',
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='invitation_responses'
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Convite de motorista'
        verbose_name_plural = 'Convites de motoristas'
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=['travel'], condition=models.Q(is_current=True), name='invitation_one_current'
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F('created_at')), name='invitation_expiry_order'
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status='pending', responded_at__isnull=True, responded_by__isnull=True, closed_at__isnull=True
                    )
                    | models.Q(
                        status__in=['accepted', 'declined'],
                        responded_at__isnull=False,
                        responded_by__isnull=False,
                        closed_at__isnull=False,
                    )
                    | models.Q(
                        status__in=['expired', 'revoked'],
                        responded_at__isnull=True,
                        responded_by__isnull=True,
                        closed_at__isnull=False,
                    )
                ),
                name='invitation_status_audit',
            ),
            models.CheckConstraint(
                condition=models.Q(responded_at__isnull=True)
                | models.Q(responded_at__gte=models.F('created_at'), responded_at__lt=models.F('expires_at')),
                name='invitation_response_inside_window',
            ),
            models.CheckConstraint(
                condition=models.Q(closed_at__isnull=True) | models.Q(closed_at__gte=models.F('created_at')),
                name='invitation_closed_after_creation',
            ),
        ]

    def __str__(self):
        return f'Convite #{self.pk}'

    def clean(self):
        super().clean()
        travel = related_values(self, 'travel', 'company_id', 'service_day_id')
        driver = related_values(self, 'driver_membership', 'company_id', 'driver_id', 'status', 'driver__user_id')
        errors = {}
        if travel and travel['service_day_id'] is None:
            errors['travel'] = 'O convite exige viagem datada.'
        if driver and (driver['driver_id'] is None or (self.status == 'pending' and driver['status'] != 'active')):
            errors['driver_membership'] = 'O convite exige vínculo ativo de motorista.'
        if travel and driver and travel['company_id'] != driver['company_id']:
            errors['driver_membership'] = 'O motorista deve pertencer à empresa da viagem.'
        if driver and self.responded_by_id and driver['driver__user_id'] != self.responded_by_id:
            errors['responded_by'] = 'Somente o motorista convidado pode responder.'
        if errors:
            raise ValidationError(errors)


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='operational_notices'
    )
    kind = models.CharField(max_length=20)
    resource_type = models.CharField(max_length=20)
    resource_id = models.CharField(max_length=64, validators=[RegexValidator(r'^[1-9]\d*$')])
    deduplication_key = models.CharField(max_length=128)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Aviso operacional'
        verbose_name_plural = 'Avisos operacionais'
        ordering = ('-created_at', '-pk')
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['recipient', 'deduplication_key'], name='notice_recipient_deduplication'),
            models.CheckConstraint(
                condition=models.Q(read_at__isnull=True) | models.Q(read_at__gte=models.F('created_at')),
                name='notice_read_after_creation',
            ),
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=[
                        'membership',
                        'request',
                        'invitation',
                        'cancellation',
                        'publication',
                        'revision',
                        'operation',
                    ]
                ),
                name='notice_kind_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(resource_type__in=['membership', 'service_day', 'request', 'travel', 'invitation']),
                name='notice_resource_type_valid',
            ),
        ]

    def __str__(self):
        return f'Aviso #{self.pk}'

    def clean(self):
        super().clean()
        allowed_statuses = {
            'pending',
            'active',
            'ended',
            'approved',
            'rejected',
            'withdrawn',
            'expired',
            'superseded',
            'preparing',
            'applied',
            'failed',
            'published',
            'canceled',
            'scheduled',
            'in_progress',
            'finished',
            'accepted',
            'declined',
            'revoked',
        }
        payload = self.payload
        if not isinstance(payload, dict) or set(payload) - {'revision', 'status'}:
            raise ValidationError({'payload': 'O aviso aceita somente status e revisão, sem dados pessoais.'})
        if 'revision' in payload and (type(payload['revision']) is not int or payload['revision'] < 1):
            raise ValidationError({'payload': 'A revisão deve ser um inteiro positivo.'})
        if 'status' in payload and (
            not isinstance(payload['status'], str) or payload['status'] not in allowed_statuses
        ):
            raise ValidationError({'payload': 'Status de aviso inválido.'})
