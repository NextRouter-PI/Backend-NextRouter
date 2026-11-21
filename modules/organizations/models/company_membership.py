from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from shared.exceptions import require


class CompanyMembershipQuerySet(models.QuerySet):
    def open(self):
        return self.filter(status__in=[CompanyMembership.Status.PENDING, CompanyMembership.Status.ACTIVE])

    def active(self):
        return self.filter(status=CompanyMembership.Status.ACTIVE)

    def visible_to(self, user):
        if not user or not user.is_authenticated or not user.is_active:
            return self.none()
        from modules.organizations.models.company import Company

        owned_company = Company.objects.operational_for(user).filter(pk=OuterRef('company_id'))
        return self.filter(Exists(owned_company) | Q(passenger__user=user) | Q(driver__user=user))


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

    objects = CompanyMembershipQuerySet.as_manager()

    class Meta:
        verbose_name = _('Vínculo empresarial')
        verbose_name_plural = _('Vínculos empresariais')
        ordering = ('-created_at', '-pk')
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=['company', 'status', 'created_at'], name='membership_company_status_idx'),
        ]
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

    @property
    def profile(self):
        return self.passenger if self.passenger_id is not None else self.driver

    @property
    def profile_user(self):
        return self.profile.user

    @property
    def is_open(self) -> bool:
        return self.status in (self.Status.PENDING, self.Status.ACTIVE)

    def transition_decision(self, *, target_status: str, actor_id, now) -> None:
        require(
            self.status == self.Status.PENDING and target_status in (self.Status.ACTIVE, self.Status.REJECTED),
            'invalid_transition',
            'Transição de vínculo inválida.',
        )
        self.status = target_status
        self.reviewed_by_id = actor_id
        self.reviewed_at = now
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

    def transition_withdraw(self, *, actor_id, now) -> None:
        require(
            self.status == self.Status.PENDING,
            'invalid_transition',
            'Apenas pedidos pendentes podem ser retirados.',
        )
        self.status = self.Status.WITHDRAWN
        self.withdrawn_by_id = actor_id
        self.withdrawn_at = now
        self.save(update_fields=['status', 'withdrawn_by', 'withdrawn_at'])

    def transition_end(self, *, actor_id, now) -> None:
        require(
            self.status == self.Status.ACTIVE,
            'invalid_transition',
            'Apenas vínculos ativos podem ser encerrados.',
        )
        self.status = self.Status.ENDED
        self.ended_by_id = actor_id
        self.ended_at = now
        self.save(update_fields=['status', 'ended_by', 'ended_at'])
