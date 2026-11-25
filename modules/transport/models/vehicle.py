from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class VehicleQuerySet(models.QuerySet):
    def for_company(self, company):
        return self.filter(company=company)

    def active(self):
        return self.filter(status=Vehicle.Status.ACTIVE)


class Vehicle(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Ativo')
        MAINTENANCE = 'maintenance', _('Manutenção')

    class VehicleType(models.TextChoices):
        VAN = 'van', _('Van')
        MICROBUS = 'microbus', _('Micro-ônibus')
        BUS = 'bus', _('Ônibus')
        CAR = 'car', _('Carro')
        OTHER = 'other', _('Outro')

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

    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.VAN,
        verbose_name=_('Tipo de veículo'),
    )

    brand = models.CharField(
        max_length=60,
        blank=True,
        verbose_name=_('Marca'),
    )

    model = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Modelo'),
    )

    seats = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Assentos'),
        help_text=_('Quantidade de assentos; a capacidade é o máximo de passageiros permitido.'),
    )

    notes = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name=_('Informações adicionais'),
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

    objects = VehicleQuerySet.as_manager()

    class Meta:
        verbose_name = _('Veículo')
        verbose_name_plural = _('Veículos')
        db_table = 'router_vehicles'
        ordering = ('plate',)
        constraints = (
            models.CheckConstraint(condition=models.Q(capacity__gte=1), name='vehicle_capacity_positive'),
            models.CheckConstraint(
                condition=models.Q(seats__isnull=True) | models.Q(seats__gte=1),
                name='vehicle_seats_positive',
            ),
        )

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
