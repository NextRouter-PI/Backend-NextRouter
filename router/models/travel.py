from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.company import Company
from authenticator.models.driver import Driver
from router.models.path import Path


class Travel(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', _('Agendada')
        IN_PROGRESS = 'in_progress', _('Em andamento')
        FINISHED = 'finished', _('Finalizada')
        CANCELED = 'canceled', _('Cancelada')

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        verbose_name=_('Empresa'),
        related_name='travels',
    )

    driver = models.ForeignKey(
        Driver,
        on_delete=models.PROTECT,
        verbose_name=_('Motorista'),
        related_name='travels',
    )

    path = models.ForeignKey(
        Path,
        on_delete=models.CASCADE,
        verbose_name=_('Rota (Path)'),
        related_name='travels',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        verbose_name=_('Status'),
        db_index=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Data de início'),
        db_index=True,
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Data de término'),
    )

    # Última localização conhecida do motorista durante a viagem, atualizada via WebSocket.
    # Usa campos float simples (não GeoDjango/PointField) para não depender de GDAL/PostGIS.
    current_latitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Latitude atual'),
    )

    current_longitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Longitude atual'),
    )

    location_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Última atualização de localização'),
    )

    class Meta:
        verbose_name = _('Viagem')
        verbose_name_plural = _('Viagens')
        db_table = 'router_travel'
        ordering = ('-started_at',)

    def __str__(self):
        day = self.started_at.day if self.started_at else '?'
        return f'Viagem do dia {day} da empresa {self.company.user.name.title()}'
