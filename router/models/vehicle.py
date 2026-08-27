from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.company_route_group import CompanyRouteGroup
from authenticator.models.driver import Driver


class Vehicle(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Ativo')
        MAINTENANCE = 'maintenance', _('Manutenção')

    route_group = models.ForeignKey(
        CompanyRouteGroup,
        on_delete=models.PROTECT,
        verbose_name=_('Grupo de Rotas'),
        related_name='vehicles',
    )

    driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('Motorista responsável'),
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

    model = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Modelo'),
    )

    year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Ano'),
    )

    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Capacidade'),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_('Status'),
    )

    color = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Cor'),
    )

    features = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Características'),
        help_text=_('Lista de comodidades, ex.: ["Ar-condicionado", "Wi-Fi", "Cinto de segurança"]'),
    )

    class Meta:
        verbose_name = _('Veículo')
        verbose_name_plural = _('Veículos')
        db_table = 'router_vehicles'
        ordering = ('route_group__name',)

    def __str__(self):
        return f'Veículo de placa {self.plate} - {self.route_group.company.user.name.title()}'
