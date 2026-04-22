from django.db import models
from django.utils.translation import gettext_lazy as _

from .user import User


class Empresa(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name='company_profile',
    )
    razao_social = models.CharField(max_length=255, verbose_name=_('Razão Social'))
    cnpj = models.CharField(max_length=18, unique=True, verbose_name=_('CNPJ'))
    inscricao_estadual = models.CharField(max_length=30, blank=True, null=True, verbose_name=_('Inscrição Estadual'))
    responsavel_nome = models.CharField(max_length=255, verbose_name=_('Responsável'))
    responsavel_cpf = models.CharField(max_length=14, blank=True, null=True, verbose_name=_('CPF do Responsável'))
    telefone_comercial = models.CharField(max_length=20, blank=True, null=True, verbose_name=_('Telefone Comercial'))
    endereco = models.CharField(max_length=255, blank=True, null=True, verbose_name=_('Endereço'))
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Cidade'))
    estado = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Estado'))
    cep = models.CharField(max_length=10, blank=True, null=True, verbose_name=_('CEP'))
    valor_mensal = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00, verbose_name=_('Valor mensal'), blank=True, null=True
    )
    data_de_registro = models.DateTimeField(auto_now_add=True, verbose_name=_('Criado em'))

    def __str__(self):
        return f'{self.user.name} - {self.responsavel_nome} ({self.user.email})'
