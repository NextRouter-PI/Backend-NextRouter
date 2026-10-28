import uuid
from typing import ClassVar

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.accounts.validators.cpf import validate_cpf
from modules.uploads.models import Image
from shared.address import GeocodableAddressMixin


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError(_('The given email address must be set.'))

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self._create_user(email, password, **extra_fields)


class User(GeocodableAddressMixin, AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        _('name'),
        max_length=255,
        blank=False,
    )

    email = models.EmailField(
        _('email address'),
        unique=True,
        blank=False,
    )

    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. Unselect this instead of deleting accounts.'
        ),
    )

    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )

    phone = models.CharField(
        max_length=11,
        blank=True,
        verbose_name=_('Telefone'),
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
        help_text=_('Número da casa/apartamento. Use "S/N" quando não houver numeração.'),
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

    profile_picture = models.OneToOneField(
        Image,
        null=True,
        verbose_name=_('Foto de perfil'),
        blank=True,
        on_delete=models.SET_NULL,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name=_('Data de criação'),
    )

    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )

    cpf = models.CharField(
        max_length=11,
        blank=False,
        null=False,
        verbose_name=_('CPF'),
        validators=[validate_cpf],
    )

    birthday = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Data de nascimento'),
    )

    objects: UserManager = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: ClassVar[list[str]] = ['name']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering: ClassVar[list[str]] = ['-created_at']

    def __str__(self) -> str:
        return f'{self.name} <{self.email}>' if self.name else self.email

    def get_full_name(self) -> str:
        return self.name.strip()

    def get_short_name(self) -> str:
        return self.name.split()[0] if self.name else self.email

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
