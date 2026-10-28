from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.accounts.models.user import User
from modules.organizations.models.company_route_group import CompanyRouteGroup
from modules.uploads.models.document import Document


class Driver(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Motorista (Usuário)'),
        related_name='driver',
        unique=True,
    )

    route_group = models.ForeignKey(
        CompanyRouteGroup,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        verbose_name=_('Grupo de Rota'),
        related_name='drivers',
    )

    is_approved = models.BooleanField(
        default=False,
        verbose_name=_('Aprovado na empresa'),
        db_index=True,
    )
    is_rejected = models.BooleanField(default=False)

    cnh = models.OneToOneField(
        Document,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cnh',
        verbose_name=_('CNH'),
    )

    class Meta:
        verbose_name = _('Motorista')
        verbose_name_plural = _('Motoristas')
        constraints = (
            models.CheckConstraint(
                condition=~(models.Q(is_approved=True) & models.Q(is_rejected=True)),
                name='driver_not_approved_and_rejected',
            ),
        )
        db_table = 'authenticator_driver'
        ordering = ('user__name',)

    def __str__(self):
        if self.route_group and self.route_group.company:
            company_name = self.route_group.company.user.name.title()
            route_name = self.route_group.name.title()
            return f'{self.user.name.title()} (Rota {route_name} de {company_name})'
        return f'{self.user.name.title()} (Sem rota atribuída)'

    @property
    def review_status(self) -> str:
        return 'approved' if self.is_approved else 'rejected' if self.is_rejected else 'pending'
