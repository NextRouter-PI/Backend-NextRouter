from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.company_route_group import CompanyRouteGroup


class Path(models.Model):
    points = models.JSONField(verbose_name=_('Pontos de Parada'))

    route_group = models.ForeignKey(
        CompanyRouteGroup,
        verbose_name=_('Grupo de Rotas'),
        related_name='paths',
        on_delete=models.CASCADE,
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_('Nome da Rota'),
    )

    class Meta:
        verbose_name = _('Rota')
        verbose_name_plural = _('Rotas')
        db_table = 'router_path'
        ordering = (
            'route_group',
            'name',
        )

    def __str__(self):
        return f'{self.name.title()} ({self.route_group.name.title()})'
