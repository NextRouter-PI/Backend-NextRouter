from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.route import Route
from core.models.user import User


class LostItem(models.Model):
    route_id = models.ForeignKey(
        Route, on_delete=models.PROTECT, null=False, blank=False, verbose_name=_('Rota'), related_name='lost_items'
    )
    user_id = models.ForeignKey(
        User, on_delete=models.PROTECT, null=False, blank=False, verbose_name=_('Usuário'), related_name='lost_items'
    )

    item_description = models.TextField(
        max_length=50,
        null=False,
        blank=False,
        verbose_name=_('Descrição do item'),
    )

    def __str__(self):
        return f'{self.route_id}'

    class Meta:
        verbose_name = 'Item Perdido'
        verbose_name_plural = 'Itens Perdidos'
        db_table = 'core.lost_item'
