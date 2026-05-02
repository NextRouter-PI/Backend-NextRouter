from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.company import Company


class CompanyRouteGroup(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, null=False, blank=False)

    name = models.CharField(max_length=100, null=False, blank=False, verbose_name=_('nome da rota'))
    commom_address = models.CharField(
        max_length=9,
        blank=False,
        null=False,
        verbose_name=_('Endereço em comum dentre os passageiros'),
        help_text=_('CEP do endereço'),
    )

    class Meta:
        verbose_name = 'Grupo de Rota da Empresa'
        verbose_name_plural = 'Grupos de Rotas das Empresas'

    def __str__(self):
        return f'Rota {str(self.name.capitalize())}'
