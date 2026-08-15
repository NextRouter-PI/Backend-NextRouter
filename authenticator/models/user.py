from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.validators.cpf import validate_cpf
from uploader.models import Image


# Código de https://github.com/sesh/django-authuser/blob/19e046c54f6988d33ac9e2bc5aa5f86bccae1e1f/models.py#L42.
# Apenas as mensagens de erro foram adaptadas para o português.
class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('O endereço de e-mail deve ser informado.')

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superusuário precisa ter is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superusuário precisa ter is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        max_length=255,
        unique=True,
    )

    name = models.CharField(
        max_length=255,
        blank=False,
        null=False,
        verbose_name=_('Nome'),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Usuário está ativo'),
    )

    is_staff = models.BooleanField(
        default=False,
        verbose_name=_('Usuário é da equipe'),
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

    REQUIRED_FIELDS = ()

    def __str__(self):
        return f'{self.name.title()}'

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        db_table = 'authenticator_user'
