from django.db import models
from django.utils.translation import gettext_lazy as _

from .company import Company
from .user import User


class Passenger(models.Model):

    id = models.BigAutoField(primary_key=True)

    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name="passenger_profile",
        verbose_name=_("Usuário")
    )

    empresa = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="passageiros",
        verbose_name=_("Empresa"),
        blank=True,
        null=True
    )

    cpf = models.CharField(
        max_length=14,
        unique=True,
        verbose_name=_("CPF")
    )

    data_nascimento = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Data de nascimento")
    )

    genero = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Gênero")
    )

    endereco = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Endereço")
    )

    cidade = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Cidade")
    )

    estado = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Estado")
    )

    cep = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name=_("CEP")
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Criado em")
    )

    class Meta:
        db_table = "passengers"
        verbose_name = "Passageiro"
        verbose_name_plural = "Passageiros"
        ordering = ["-created_at"]

    def __str__(self):
        return self.user.nome or self.user.email
