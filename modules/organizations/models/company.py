from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.accounts.models.user import User
from modules.organizations.validators.cnpj import validate_cnpj
from modules.uploads.models.document import Document
from shared.address import GeocodableAddressMixin


class Company(GeocodableAddressMixin, models.Model):
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

    cep = models.CharField(
        max_length=9,
        blank=True,
        verbose_name=_('CEP'),
    )

    street = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Rua'),
    )

    number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Número'),
    )

    complement = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Complemento'),
    )

    neighborhood = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Bairro'),
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Cidade'),
    )

    state = models.CharField(
        max_length=2,
        blank=True,
        verbose_name=_('Estado (UF)'),
    )

    latitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Latitude'),
    )

    longitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_('Longitude'),
    )

    geocoded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Data da geocodificação do endereço'),
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
    is_rejected = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_companies'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('Empresa')
        verbose_name_plural = _('Empresas')
        db_table = 'authenticator_company'
        ordering = ('trade_name',)
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=~(models.Q(is_approved=True) & models.Q(is_rejected=True)),
                name='company_not_approved_and_rejected',
            )
        ]

    def __str__(self):
        return self.trade_name.title()

    @property
    def review_status(self) -> str:
        return 'approved' if self.is_approved else 'rejected' if self.is_rejected else 'pending'
