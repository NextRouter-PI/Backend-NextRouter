from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.user import User
from router.models.travel import Travel


class LostItem(models.Model):
    class Status(models.TextChoices):
        REPORTED = 'reported', _('Relatado')
        FOUND = 'found', _('Encontrado')
        RETURNED = 'returned', _('Devolvido')

    travel = models.ForeignKey(Travel, on_delete=models.PROTECT, verbose_name=_('Viagem'), related_name='lost_items')

    user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name=_('Usuário'), related_name='lost_items')

    item_description = models.CharField(
        max_length=255,
        verbose_name=_('Descrição do item'),
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REPORTED, verbose_name=_('Status'))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Data de registro'))

    class Meta:
        verbose_name = _('Item Perdido')
        verbose_name_plural = _('Itens Perdidos')
        db_table = 'router_lost_item'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.item_description[:30]} - {self.user.name}'
