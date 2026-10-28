from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.accounts.models.user import User
from modules.organizations.models.company_route_group import CompanyRouteGroup


class Passenger(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Passageiro (Usuário)'),
        related_name='passenger',
        unique=True,
        null=False,
        blank=False,
    )

    route_group = models.ForeignKey(
        CompanyRouteGroup,
        on_delete=models.PROTECT,
        verbose_name=_('Grupo de Rota'),
        null=True,
        blank=True,
        related_name='passengers',
        db_index=True,
    )

    is_approved = models.BooleanField(
        default=False,
        null=False,
        verbose_name=_('Aprovado na empresa'),
    )
    is_rejected = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('Passageiro')
        verbose_name_plural = _('Passageiros')
        db_table = 'authenticator_passenger'
        ordering = ('user__name',)
        constraints = (
            models.CheckConstraint(
                condition=~(models.Q(is_approved=True) & models.Q(is_rejected=True)),
                name='passenger_not_approved_and_rejected',
            ),
        )

    def __str__(self):
        return self.user.name.title() if self.user else _('Passageiro sem usuário')

    @property
    def review_status(self) -> str:
        return 'approved' if self.is_approved else 'rejected' if self.is_rejected else 'pending'
