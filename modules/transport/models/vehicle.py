from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Vehicle(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Ativo')
        MAINTENANCE = 'maintenance', _('Manutenção')

    company = models.ForeignKey('organizations.Company', on_delete=models.PROTECT, related_name='fleet')
    garage_point = models.ForeignKey(
        'organizations.OperationalPoint',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='garaged_vehicles',
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
        ordering = ('plate',)
        constraints = (models.CheckConstraint(condition=models.Q(capacity__gte=1), name='vehicle_capacity_positive'),)

    def __str__(self):
        return f'Veículo de placa {self.plate}'

    def clean(self):
        super().clean()
        from .validation import related_values

        point = related_values(self, 'garage_point', 'company_id', 'point_type')
        if point and self.company_id is not None and point['company_id'] != self.company_id:
            raise ValidationError('A garagem deve pertencer à empresa do veículo.')
        if point and point['point_type'] != 'garage':
            raise ValidationError('O ponto selecionado para o veículo deve ser do tipo garagem.')
