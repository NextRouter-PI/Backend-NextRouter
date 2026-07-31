# from django.contrib.gis.db import models as geo_models
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.company import Company
from core.models.driver import Driver


class Travel(models.Model):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_('Empresa'),
        related_name='travels',
    )
    driver_id = models.ForeignKey(
        Driver,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_('Motorista'),
        related_name='travels',
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Data de início'))

    finished_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Data de término'))

    # real_time_driver_tracking = geo_models.PointField(
    # verbose_name=_('Localização real do motorista:'), null=True, blank=True
    # )

    def __str__(self):
        return f'Viagem do dia {self.started_at.day} da empresa {self.company_id.user.name.title()}'

    class Meta:
        verbose_name = 'Viagem'
        verbose_name_plural = 'Viagens'
        db_table = 'router.travel'
        # required_db_features = ['gis_enabled']
