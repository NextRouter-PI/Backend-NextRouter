from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.company_route_group import CompanyRouteGroup


class Path(models.Model):
    points = models.JSONField(verbose_name=_('Pontos de Parada'))
    group_id = models.ForeignKey(
        CompanyRouteGroup, verbose_name=_('Grupo de Rotas'), related_name='rotas', on_delete=models.CASCADE
    )

    name = models.CharField(max_length=100, null=False, blank=False, verbose_name=_('Nome da Rota'))

    def __str__(self):
        return f'Rota {self.name.title()}'

    class Meta:
        verbose_name = 'Rota'
        verbose_name_plural = 'Rotas'
        db_table = 'routes.path'
