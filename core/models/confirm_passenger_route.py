from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.travel import Travel
from core.models.user import User


class ConfirmPassengerRoute(models.Model):
    route_id = models.ForeignKey(
        Travel,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_('Rota'),
        related_name='passenger_confirms',
    )
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_('Usuário'),
        related_name='passenger_confirms',
    )

    confirm = models.BooleanField(null=True, blank=True, verbose_name=_('Confirmado'))

    def __str__(self):
        return f'Confirmação de {self.user_id.name.title()} na {self.route_id}'

    class Meta:
        verbose_name = 'Confirmação de Usuário na Rota'
        verbose_name_plural = 'Confirmações de Usuários na Rotas'
        db_table = 'core.confirm_passenger_route'
