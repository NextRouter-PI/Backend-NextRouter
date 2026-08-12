from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.user import User
from authenticator.validators.cnpj import validate_cnpj
from uploader.models.document import Document


class Company(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Empresa (Usuário)'),
        related_name='company',
        unique=True,
    )

    trade_name = models.CharField(
        max_length=255,
        verbose_name=_('Nome Fantasia'),
    )

    legal_name = models.CharField(
        max_length=255,
        verbose_name=_('Razão Social'),
    )

    cnpj = models.CharField(
        max_length=14,
        unique=True,
        verbose_name=_('CNPJ'),
        validators=[validate_cnpj],
    )

    state_registration = models.CharField(
        max_length=20,
        verbose_name=_('Inscrição Estadual'),
    )

    contact_phone = models.CharField(
        max_length=11,
        verbose_name=_('Telefone de contato'),
        blank=True,
    )

    contact_email = models.EmailField(
        max_length=255,
        verbose_name=_('Email de contato'),
        blank=True,
    )

    articles_of_association_document = models.OneToOneField(
        Document,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Contrato Social'),
    )

    state_operating_license_document = models.OneToOneField(
        Document,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Licença de Operação'),
    )

    certificate_of_good_stading_document = models.OneToOneField(
        Document,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('Certidões Negativas'),
    )

    is_approved = models.BooleanField(
        default=False,
        verbose_name=_('Aprovada no sistema'),
        db_index=True,
    )

    class Meta:
        verbose_name = _('Empresa')
        verbose_name_plural = _('Empresas')
        db_table = 'accounts_company'
        ordering = ('trade_name',)

    def __str__(self):
        return self.trade_name.title()
