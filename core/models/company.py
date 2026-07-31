from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models.user import User
from core.validators.cnpj import validate_cnpj
from core.validators.email import validate_email
from uploader.models.document import Document


class Company(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Empresa (Usuário)'),
        null=False,
        blank=False,
        unique=True,
        related_name='company',
    )

    contact_phone = models.CharField(
        max_length=11,
        verbose_name=_('Telefone de contato/Telefone comercial'),
        null=True,
        blank=True,
    )

    contact_email = models.EmailField(
        max_length=255,
        verbose_name=_('Email de contato'),
        null=True,
        blank=True,
        validators=[validate_email],
    )

    cnpj = models.CharField(max_length=14, unique=True, verbose_name=_('CNPJ'), validators=[validate_cnpj])

    articles_of_association_document = models.OneToOneField(
        Document,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Documento de Contrato Social'),
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
        default=False,
        verbose_name=_('Empresa aprovada no sistema'),
        null=False,
        blank=False,
    )

    trade_name = models.CharField(null=False, verbose_name=_('Nome Fantasia'))

    legal_name = models.CharField(null=False, verbose_name=_('Razão Social'))

    state_registration = models.CharField(null=False, verbose_name=_('Inscrição Estadual'))

    def __str__(self):
        return f'{self.user.name.title()}'

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        db_table = 'accounts_company'
