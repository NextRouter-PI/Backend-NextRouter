from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.user import User
from core.models.company import Company
from core.models.driver import Driver
from django.contrib.gis.db import models as geo_models


class Route(models.Model):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_("Empresa"),
    )
    driver_id = models.ForeignKey(
        Driver,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_("Motorista"),
    )
    started_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Data de início")
    )

    finished_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Data de término")
    )

    real_time_driver_tracking = geo_models.PointField(
        verbose_name=_("Localização real do motorista:"), null=True, blank=True
    )

    def __str__(self):
        return f"Rota {self.id.title()} da empresa {self.company_id.title()}"

    class Meta:
        verbose_name = "Rota"
        verbose_name_plural = "Rotas"
