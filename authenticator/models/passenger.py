from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.company_route_group import CompanyRouteGroup
from authenticator.models.user import User


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

    class Meta:
        verbose_name = _('Passageiro')
        verbose_name_plural = _('Passageiros')
        db_table = 'authenticator_passenger'
        ordering = ('user__name',)

    def __str__(self):
        return self.user.name.title() if self.user else _('Passageiro sem usuário')
