from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.company import Company


class CompanyRouteGroup(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        verbose_name=_('Empresa'),
        related_name='route_groups',
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_('Nome do Grupo'),
    )

    common_cep = models.CharField(
        max_length=9,
        verbose_name=_('CEP em comum'),
        help_text=_('CEP do endereço comum aos passageiros'),
    )

    reference_latitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Latitude de referência'),
        help_text=_('Ponto central da área de captação do grupo, usado para calcular rotas e paradas.'),
    )

    reference_longitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Longitude de referência'),
    )

    geocoded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Data da geocodificação'),
    )

    class Meta:
        verbose_name = _('Grupo de Rota')
        verbose_name_plural = _('Grupos de Rotas')
        db_table = 'authenticator_company_route_group'
        constraints = (models.UniqueConstraint(fields=['company', 'name'], name='unique_company_route_name'),)
        ordering = (
            'company',
            'name',
        )

    def __str__(self):
        return f'{self.name.title()} ({self.company.trade_name})'
