from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.organizations.models.company_route_group import CompanyRouteGroup
from modules.organizations.models.driver import Driver


class Vehicle(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Ativo')
        MAINTENANCE = 'maintenance', _('Manutenção')

    company = models.ForeignKey(
        'organizations.Company', on_delete=models.PROTECT, null=True, blank=True, related_name='fleet'
    )
    garage_point = models.ForeignKey(
        'organizations.OperationalPoint',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='garaged_vehicles',
    )

    route_group = models.ForeignKey(
        CompanyRouteGroup,
        on_delete=models.PROTECT,
        verbose_name=_('Grupo de Rotas'),
        related_name='vehicles',
        null=True,
        blank=True,
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
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(company__isnull=True, route_group__isnull=False)
                    | models.Q(company__isnull=False, route_group__isnull=True)
                ),
                name='vehicle_one_ownership_path',
            ),
            models.CheckConstraint(
                condition=models.Q(capacity__isnull=True) | models.Q(capacity__gte=1), name='vehicle_capacity_positive'
            ),
            models.CheckConstraint(
                condition=models.Q(company__isnull=True) | models.Q(capacity__isnull=False),
                name='company_vehicle_capacity_known',
            ),
        )

    def __str__(self):
        return f'Veículo de placa {self.plate}'

    def clean(self):
        super().clean()
        from .validation import related_values

        point = related_values(self, 'garage_point', 'company_id')
        group = related_values(self, 'route_group', 'company_id')
        company_id = self.company_id or (group['company_id'] if group else None)
        if point and company_id is not None and point['company_id'] != company_id:
            raise ValidationError('A garagem deve pertencer à empresa do veículo.')
