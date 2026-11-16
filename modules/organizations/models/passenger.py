from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.accounts.models.user import User


class Passenger(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Passageiro (Usuário)'),
        related_name='passenger',
        unique=True,
        null=False,
        blank=False,
    )

    class Meta:
        verbose_name = _('Passageiro')
        verbose_name_plural = _('Passageiros')
        db_table = 'authenticator_passenger'
        ordering = ('user__name',)

    def __str__(self):
        return self.user.name.title() if self.user else _('Passageiro sem usuário')
