from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.company_route_group import CompanyRouteGroup
from core.models.user import User
from uploader.models.document import Document


class Driver(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, verbose_name=_('Usuário'))
    group_route = models.OneToOneField(
        CompanyRouteGroup, blank=True, null=True, on_delete=models.PROTECT, verbose_name=_('Grupo de Rota')
    )
    is_approved = models.BooleanField(default=False, null=False, verbose_name=_('Aprovado na empresa'))

    cnh = models.OneToOneField(
        Document,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('CNH'),
    )

    def __str__(self):
        if self.group_route:
            return f'{self.user.name.title()} (Rota {self.group_route.name.title()} de {self.group_route.company.user.name.title()})'
        return f'{self.user.name.title()} (Sem rota atribuída)'

    class Meta:
        verbose_name = 'Motorista'
        verbose_name_plural = 'Motoristas'
