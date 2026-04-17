from django.db import models
from django.utils.translation import gettext_lazy as _

from .company import Company
from .user import User


class Driver(models.Model):

    id = models.BigAutoField(primary_key=True)

    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name="driver_profile",
        verbose_name=_("Usuário")
    )

    empresa = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="motoristas",
        verbose_name=_("Empresa"),
        blank=True,
        null=True
    )

    cpf = models.CharField(
        max_length=14,
        unique=True,
        verbose_name=_("CPF")
    )

    cnh = models.CharField(
        max_length=30,
        unique=True,
        verbose_name=_("CNH")
    )

    aprovado = models.BooleanField(
        default=False,
        verbose_name=_("Aprovado")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Criado em")
    )

    class Meta:
        db_table = "drivers"
        verbose_name = "Motorista"
        verbose_name_plural = "Motoristas"
        ordering = ["-created_at"]

    def __str__(self):
        return self.user.nome or self.user.email
