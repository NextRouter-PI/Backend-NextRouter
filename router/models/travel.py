# from django.contrib.gis.db import models as geo_models
from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.company import Company
from authenticator.models.driver import Driver
from router.models.path import Path


class Travel(models.Model):
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

    # location = geo_models.PointField(verbose_name=_('Localização atual'), null=True, blank=True)

    class Meta:
        verbose_name = _('Viagem')
        verbose_name_plural = _('Viagens')
        db_table = 'router_travel'
        ordering = ('-started_at',)
        # required_db_features = ['gis_enabled']

    def __str__(self):
        return f'Viagem do dia {self.started_at.day} da empresa {self.company_id.user.name.title()}'
