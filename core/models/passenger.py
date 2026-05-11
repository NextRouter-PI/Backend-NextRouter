from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.company_route_group import CompanyRouteGroup
from core.models.user import User


class Passenger(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, verbose_name=_('Usuário'))
    group_route = models.OneToOneField(CompanyRouteGroup, on_delete=models.PROTECT, verbose_name=_('Grupo de Rota'))
    is_approved = models.BooleanField(default=False, null=False, verbose_name=_('Aprovado na empresa'))

    def __str__(self):
        return f'{self.user.name.title()} (Rota {self.group_route.name.title()} de {self.group_route.company.user.name.title()})'

    class Meta:
        verbose_name = 'Passageiro'
        verbose_name_plural = 'Passageiros'
