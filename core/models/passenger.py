from django.db import models

from core.models.user import User


class Passageiro(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name="passageiro"
    )

    telefone = models.CharField(max_length=20, blank=True)
    data_de_registro = models.DateTimeField(auto_now_add=True)

    cpf = models.CharField(max_length=14, unique=True)
    data_nascimento = models.DateField()

    genero = models.CharField(max_length=20, blank=True)
    endereco = models.CharField(max_length=255, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True)
    cep = models.CharField(max_length=20, blank=True)

    empresa = models.ForeignKey(
        "Empresa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="passageiros"
    )

    def __str__(self):
        return f"{self.user.name} ({self.user.email})"
