from django.db import models
from django.utils.translation import gettext_lazy as _

from uploader.models import Document

from .user import User


class Company(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.PROTECT, verbose_name=_('Empresa (Usuário)'), null=False, blank=False
    )
    contact_phone = models.CharField(
        max_length=11, verbose_name=_('Telefone de contato/Telefone comercial'), null=True, blank=True
    )
    contact_email = models.EmailField(max_length=255, verbose_name=_('Email de contato'), null=True, blank=True)
    cnpj = models.CharField(max_length=14, unique=True, verbose_name=_('CNPJ'))
    articles_of_association_document = models.OneToOneField(
        Document, null=True, on_delete=models.SET_NULL, related_name='+', verbose_name=_('Documento de Contrato Social')
    )
    state_operating_license_document = models.OneToOneField(
        Document,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Documento de Licensa de Operação Estadual'),
    )
    certificate_of_good_stading_document = models.OneToOneField(
        Document,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Documento de Certidões Negativas'),
    )
    is_approved = models.BooleanField(
        default=False, verbose_name=_('Empresa aprovada no sistema'), null=False, blank=False
    )

    def __str__(self):
        return f'{self.user.name.title()}'

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
