from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.user import User
from core.models.route import Route


class ConfirmPassengerRoute(models.Model):
    route_id = models.ForeignKey(
        Route, on_delete=models.PROTECT, null=False, blank=False, verbose_name=_("Rota")
    )
    user_id = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_("Usuário"),
    )

    def __str__(self):
        return f"{self.name.title()}"

    class Meta:
        verbose_name = "Confirmação de Usuário na Rota"
        verbose_name_plural = "Confirmações de Usuários na Rotas"
