from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.company_route_group import CompanyRouteGroup


class Vehicle(models.Model):
    route_group = models.ForeignKey(
        CompanyRouteGroup,
        on_delete=models.PROTECT,
        verbose_name=_('Grupo de Rotas'),
        related_name='vehicles',
    )

    garage_cep = models.CharField(
        max_length=9,
        blank=True,
        verbose_name=_('CEP da garagem'),
    )

    plate = models.CharField(
        max_length=10,
        verbose_name=_('Placa'),
        unique=True,
        help_text=_('Placa do veículo'),
    )

    class Meta:
        verbose_name = _('Veículo')
        verbose_name_plural = _('Veículos')
        db_table = 'router_vehicles'
        ordering = ('group__name',)

    def __str__(self):
        return f'Veículo de placa {self.plate} - {self.group.company.user.name.title()}'
