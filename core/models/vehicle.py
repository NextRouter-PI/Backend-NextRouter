from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.company_route_group import CompanyRouteGroup


class Vehicle(models.Model):
    group_id = models.ForeignKey(
        CompanyRouteGroup,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_('Grupo de Rotas'),
        related_name='vehicles',
    )
    garage = models.CharField(max_length=9, blank=True, null=True, verbose_name=_('CEP'))

    def __str__(self):
        return f'Veículo {self.id} da empresa {self.group_id.company.user.name}'

    class Meta:
        verbose_name = 'Veículo'
        verbose_name_plural = 'Veículos'
        db_table = 'routes_vehicles'
