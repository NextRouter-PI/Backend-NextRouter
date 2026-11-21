from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from .validation import related_values


class DriverInvitationQuerySet(models.QuerySet):
    def current(self):
        return self.filter(is_current=True)

    def expired_pending(self, *, now=None):
        moment = now or timezone.now()
        return self.filter(status=DriverInvitation.Status.PENDING, expires_at__lte=moment)

    def visible_to(self, user):
        if not user or not user.is_authenticated or not user.is_active:
            return self.none()
        from modules.organizations.models import Company, CompanyMembership

        owned_company = Company.objects.operational_for(user).filter(pk=OuterRef('travel__company_id'))
        return self.filter(
            Exists(owned_company)
            | Q(
                driver_membership__driver__user=user,
                driver_membership__status=CompanyMembership.Status.ACTIVE,
                travel__company__is_approved=True,
                travel__company__is_rejected=False,
                travel__company__user__is_active=True,
            )
        )


class DriverInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        ACCEPTED = 'accepted', 'Aceito'
        DECLINED = 'declined', 'Recusado'
        EXPIRED = 'expired', 'Expirado'
        REVOKED = 'revoked', 'Revogado'

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
        choices=Status.choices,
        default=Status.PENDING,
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='invitation_responses'
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = DriverInvitationQuerySet.as_manager()

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

    def accept(self, *, actor_id, now) -> None:
        self.status = self.Status.ACCEPTED
        self.responded_by_id = actor_id
        self.responded_at = now
        self.closed_at = now
        self.save(update_fields=['status', 'responded_by', 'responded_at', 'closed_at'])

    def decline(self, *, actor_id, now) -> None:
        self.status = self.Status.DECLINED
        self.responded_by_id = actor_id
        self.responded_at = now
        self.closed_at = now
        self.save(update_fields=['status', 'responded_by', 'responded_at', 'closed_at'])

    def expire(self, *, now) -> None:
        self.status = self.Status.EXPIRED
        self.closed_at = now
        self.is_current = False
        self.save(update_fields=['status', 'closed_at', 'is_current'])

    def revoke(self, *, now) -> None:
        self.status = self.Status.REVOKED
        self.closed_at = now
        self.is_current = False
        self.save(update_fields=['status', 'closed_at', 'is_current'])

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


class NotificationManager(models.Manager):
    def emit_bulk(
        self, *, recipients, kind: str, resource_type: str, resource_id, key: str, status: str, revision=None
    ):
        recipient_ids = sorted(set(recipients), key=str)
        if not recipient_ids:
            return []
        if status not in self.model.ALLOWED_PAYLOAD_STATUSES:
            raise ValidationError({'payload': 'Status de aviso inválido.'})
        if revision is not None and (type(revision) is not int or revision < 1):
            raise ValidationError({'payload': 'A revisão deve ser um inteiro positivo.'})
        payload = {'status': status}
        if revision is not None:
            payload['revision'] = revision
        now = timezone.now()
        notices = [
            self.model(
                recipient_id=recipient_id,
                kind=kind,
                resource_type=resource_type,
                resource_id=str(resource_id),
                deduplication_key=key,
                payload=payload,
                created_at=now,
            )
            for recipient_id in recipient_ids
        ]
        return self.bulk_create(notices, ignore_conflicts=True)


class Notification(models.Model):
    class Kind(models.TextChoices):
        MEMBERSHIP = 'membership', 'Vínculo'
        REQUEST = 'request', 'Pedido'
        INVITATION = 'invitation', 'Convite'
        CANCELLATION = 'cancellation', 'Cancelamento'
        PUBLICATION = 'publication', 'Publicação'
        REVISION = 'revision', 'Revisão'
        OPERATION = 'operation', 'Operação'

    class ResourceType(models.TextChoices):
        MEMBERSHIP = 'membership', 'Vínculo'
        SERVICE_DAY = 'service_day', 'Dia de atendimento'
        REQUEST = 'request', 'Pedido'
        TRAVEL = 'travel', 'Viagem'
        INVITATION = 'invitation', 'Convite'

    ALLOWED_PAYLOAD_STATUSES: ClassVar[frozenset[str]] = frozenset({
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
        'approaching',
    })

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

    objects = NotificationManager()

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
        payload = self.payload
        if not isinstance(payload, dict) or set(payload) - {'revision', 'status'}:
            raise ValidationError({'payload': 'O aviso aceita somente status e revisão, sem dados pessoais.'})
        if 'revision' in payload and (type(payload['revision']) is not int or payload['revision'] < 1):
            raise ValidationError({'payload': 'A revisão deve ser um inteiro positivo.'})
        if 'status' in payload and (
            not isinstance(payload['status'], str) or payload['status'] not in self.ALLOWED_PAYLOAD_STATUSES
        ):
            raise ValidationError({'payload': 'Status de aviso inválido.'})
