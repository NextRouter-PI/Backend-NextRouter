from math import isfinite
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class OperationalPoint(models.Model):
    """Ponto da empresa, independente do perfil pessoal e sem geocodificação em save."""

    class PointType(models.TextChoices):
        GARAGE = 'garage', _('Garagem')
        DESTINATION = 'destination', _('Destino')
        PASSENGER = 'passenger', _('Ponto de passageiro')

    company = models.ForeignKey('organizations.Company', on_delete=models.PROTECT, related_name='operational_points')
    point_type = models.CharField(
        max_length=20,
        choices=PointType.choices,
        default=PointType.DESTINATION,
        db_index=True,
        verbose_name=_('Tipo de ponto'),
    )
    name = models.CharField(max_length=100, verbose_name=_('Identificação'))
    street = models.CharField(max_length=255, verbose_name=_('Logradouro'))
    number = models.CharField(max_length=20, verbose_name=_('Número'))
    complement = models.CharField(max_length=255, blank=True, verbose_name=_('Complemento'))
    neighborhood = models.CharField(max_length=255, verbose_name=_('Bairro'))
    city = models.CharField(max_length=100, verbose_name=_('Cidade'))
    state = models.CharField(max_length=2, verbose_name=_('UF'))
    cep = models.CharField(max_length=9, verbose_name=_('CEP'))
    latitude = models.FloatField(verbose_name=_('Latitude'))
    longitude = models.FloatField(verbose_name=_('Longitude'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_operational_points'
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = _('Ponto operacional')
        verbose_name_plural = _('Pontos operacionais')
        ordering = ('company_id', 'pk')
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(latitude__gte=-90, latitude__lte=90), name='operational_point_latitude_range'
            ),
            models.CheckConstraint(
                condition=models.Q(longitude__gte=-180, longitude__lte=180), name='operational_point_longitude_range'
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(name='')
                    & ~models.Q(street='')
                    & ~models.Q(number='')
                    & ~models.Q(neighborhood='')
                    & ~models.Q(city='')
                    & ~models.Q(state='')
                    & ~models.Q(cep='')
                ),
                name='operational_point_required_address',
            ),
            models.CheckConstraint(
                condition=models.Q(point_type__in=('garage', 'destination', 'passenger')),
                name='operational_point_valid_type',
            ),
        ]

    def __str__(self):
        return f'Ponto #{self.pk} — empresa #{self.company_id}'

    def clean(self):
        super().clean()
        errors = {}
        for field in ('name', 'street', 'number', 'neighborhood', 'city', 'state', 'cep'):
            value = getattr(self, field)
            if not value or not str(value).strip():
                errors[field] = _('Este campo não pode ficar vazio.')
        for field, lower, upper in (('latitude', -90, 90), ('longitude', -180, 180)):
            value = getattr(self, field)
            try:
                valid = value is not None and isfinite(value) and lower <= value <= upper
            except (TypeError, ValueError):
                valid = False
            if not valid:
                errors[field] = _('Informe uma coordenada válida.')
        if errors:
            raise ValidationError(errors)
