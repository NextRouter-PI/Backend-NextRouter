from django.db import models

from .company import Empresa
from .user import User


class Motorista(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.PROTECT, related_name='driver_profile'
    )
    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name='motoristas', blank=True, null=True
    )
    cpf = models.CharField(max_length=14, unique=True, verbose_name=('CPF'))
    cnh = models.CharField(max_length=30, unique=True, verbose_name=('CNH'))
    telefone = models.CharField(max_length=20, blank=True, verbose_name=('Telefone'))
    data_nascimento = models.DateField(verbose_name=('Data de Nascimento'), blank=True, null=True)
    genero = models.CharField(max_length=20, blank=True, verbose_name=('Gênero'), null=True)
    endereco = models.CharField(max_length=255, blank=True, verbose_name=('Endereço'), null=True)
    cidade = models.CharField(max_length=100, blank=True, verbose_name=('Cidade'), null=True)
    estado = models.CharField(max_length=100, blank=True, verbose_name=('Estado'), null=True)
    cep = models.CharField(max_length=20, blank=True, verbose_name=('CEP'), null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=('Criado em'))

    def __str__(self):
        return self.user.name or self.user.email
