from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.user import User
from router.models.travel import Travel


class ConfirmPassengerRoute(models.Model):
    travel = models.ForeignKey(
        Travel,
        on_delete=models.PROTECT,
        verbose_name=_('Viagem'),
        related_name='passenger_confirms',
    )

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Usuário'),
        related_name='passenger_confirms',
    )

    confirm = models.BooleanField(
        default=False,
        verbose_name=_('Confirmado'),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Data da confirmação'),
    )

    class Meta:
        verbose_name = _('Confirmação de passageiro')
        verbose_name_plural = _('Confirmações de passageiros')
        db_table = 'router_confirm_passenger_route'
        constraints = (models.UniqueConstraint(fields=['travel', 'user'], name='unique_user_travel_confirmation'),)
        ordering = ('-created_at',)

    def __str__(self):
        return f'Confirmação de {self.user_id.name.title()} na {self.route_id}'
