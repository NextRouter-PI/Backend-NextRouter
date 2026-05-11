from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils.translation import gettext_lazy as _

from uploader.models import Image


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Usuário devem ter um email.')

        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password):
        user = self.create_user(email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=255, blank=False, null=False, verbose_name=_('Nome'))
    is_active = models.BooleanField(
        default=True, verbose_name=_('Usuário está ativo'), help_text=_('Indica que este usuário está ativo.')
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name=_('Usuário é da equipe'),
        help_text=_('Indica que este usuário pode acessar o Admin.'),
    )
    phone = models.CharField(max_length=11, blank=True, null=True, verbose_name=_('Telefone'))
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name=_('CEP'))
    profile_picture = models.OneToOneField(
        Image,
        null=True,
        verbose_name='Foto de perfil',
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name=_('Data   de criação'))

    cpf = models.CharField(max_length=11, blank=False, null=False, verbose_name=_('CPF'))

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f'{self.name.title()}'

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
