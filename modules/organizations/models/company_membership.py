from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class CompanyMembership(models.Model):
    """Ciclo empresarial autoritativo, separado da identidade e do grupo."""

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pendente')
        ACTIVE = 'active', _('Ativo')
        REJECTED = 'rejected', _('Recusado')
        WITHDRAWN = 'withdrawn', _('Retirado')
        ENDED = 'ended', _('Encerrado')

    company = models.ForeignKey('organizations.Company', on_delete=models.PROTECT, related_name='memberships')
    passenger = models.ForeignKey(
        'organizations.Passenger', on_delete=models.PROTECT, related_name='company_memberships', null=True, blank=True
    )
    driver = models.ForeignKey(
        'organizations.Driver', on_delete=models.PROTECT, related_name='company_memberships', null=True, blank=True
    )
    requested_route_group = models.ForeignKey(
        'organizations.CompanyRouteGroup',
        on_delete=models.SET_NULL,
        related_name='requested_memberships',
        null=True,
        blank=True,
        verbose_name=_('Grupo de rota solicitado'),
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        default='',
        verbose_name=_('Telefone para contato'),
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='requested_company_memberships'
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reviewed_company_memberships',
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    withdrawn_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='withdrawn_company_memberships',
        null=True,
        blank=True,
    )
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ended_company_memberships',
        null=True,
        blank=True,
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('Vínculo empresarial')
        verbose_name_plural = _('Vínculos empresariais')
        ordering = ('-created_at', '-pk')
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=(
                    models.Q(passenger__isnull=False, driver__isnull=True)
                    | models.Q(passenger__isnull=True, driver__isnull=False)
                ),
                name='membership_exactly_one_profile',
            ),
            models.UniqueConstraint(
                fields=['passenger'],
                condition=models.Q(status__in=['pending', 'active']),
                name='membership_one_open_passenger',
            ),
            models.UniqueConstraint(
                fields=['driver'],
                condition=models.Q(status__in=['pending', 'active']),
                name='membership_one_open_driver',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status__in=['pending', 'withdrawn'], reviewed_by__isnull=True, reviewed_at__isnull=True)
                    | models.Q(
                        status__in=['active', 'rejected', 'ended'],
                        reviewed_by__isnull=False,
                        reviewed_at__isnull=False,
                    )
                ),
                name='membership_review_matches_status',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status='withdrawn', withdrawn_by__isnull=False, withdrawn_at__isnull=False)
                    | (~models.Q(status='withdrawn') & models.Q(withdrawn_by__isnull=True, withdrawn_at__isnull=True))
                ),
                name='membership_withdrawal_matches_status',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status='ended', ended_by__isnull=False, ended_at__isnull=False)
                    | (~models.Q(status='ended') & models.Q(ended_by__isnull=True, ended_at__isnull=True))
                ),
                name='membership_end_matches_status',
            ),
            models.CheckConstraint(
                condition=models.Q(reviewed_at__isnull=True) | models.Q(reviewed_at__gte=models.F('created_at')),
                name='membership_review_after_request',
            ),
            models.CheckConstraint(
                condition=models.Q(withdrawn_at__isnull=True) | models.Q(withdrawn_at__gte=models.F('created_at')),
                name='membership_withdraw_after_request',
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F('reviewed_at')),
                name='membership_end_after_review',
            ),
        ]

    def __str__(self):
        return f'Vínculo #{self.pk} — empresa #{self.company_id}'
