from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.company_route_group import CompanyRouteGroup
from core.models.user import User


class Passenger(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    group_route = models.OneToOneField(CompanyRouteGroup, on_delete=models.PROTECT)
    is_approved = models.BooleanField(default=False, null=False, verbose_name=_('Passageiro aprovado na empresa'))

    def __str__(self):
        return f'Passageiro {self.user.name} (Rota {self.group_route.name} de {self.group_route.company.user.name})'

    class Meta:
        verbose_name = 'Passageiro'
        verbose_name_plural = 'Passageiros'
