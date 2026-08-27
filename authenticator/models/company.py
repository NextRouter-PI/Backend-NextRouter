from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.geocoding_mixin import GeocodableAddressMixin
from authenticator.models.user import User
from authenticator.validators.cnpj import validate_cnpj
from uploader.models.document import Document


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

    class Meta:
        verbose_name = _('Empresa')
        verbose_name_plural = _('Empresas')
        db_table = 'authenticator_company'
        ordering = ('trade_name',)

    def __str__(self):
        return self.trade_name.title()
