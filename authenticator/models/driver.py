from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.company_route_group import CompanyRouteGroup
from authenticator.models.user import User
from uploader.models.document import Document


class Driver(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Motorista (Usuário)'),
        related_name='driver',
        unique=True,
    )

    group_route = models.ForeignKey(
        CompanyRouteGroup,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        verbose_name=_('Grupo de Rota'),
        related_name='drivers',
    )

    is_approved = models.BooleanField(default=False, verbose_name=_('Aprovado na empresa'), db_index=True)

    cnh = models.OneToOneField(
        Document,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cnh',
        verbose_name=_('CNH'),
    )

    def __str__(self):
        if self.group_route and self.group_route.company:
            company_name = self.group_route.company.user.name.title()
            route_name = self.group_route.name.title()
            return f'{self.user.name.title()} (Rota {route_name} de {company_name})'
        return f'{self.user.name.title()} (Sem rota atribuída)'

    class Meta:
        verbose_name = _('Motorista')
        verbose_name_plural = _('Motoristas')
        db_table = 'accounts_driver'
        ordering = ['user__name']
