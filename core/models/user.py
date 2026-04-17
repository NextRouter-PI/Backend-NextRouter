from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Gerenciador personalizado de usuários."""

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        """Cria e salva usuário comum."""
        if not email:
            raise ValueError("O usuário precisa informar um email.")

        email = self.normalize_email(email)

        user = self.model(
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Cria superusuário."""

        extra_fields.setdefault("tipo", User.TipoUsuario.SUPERUSER)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário precisa ter is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário precisa ter is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Usuário principal do sistema."""

    class TipoUsuario(models.TextChoices):
        PASSAGEIRO = "passageiro", _("Passageiro")
        MOTORISTA = "motorista", _("Motorista")
        EMPRESA = "empresa", _("Empresa")
        SUPERUSER = "superuser", _("Superusuário")

    id = models.BigAutoField(primary_key=True)

    email = models.EmailField(
        unique=True,
        max_length=255,
        verbose_name=_("Email")
    )

    nome = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Nome")
    )

    created_at = models.DateTimeField(auto_now_add=True)

    telefone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Telefone")
    )

    tipo = models.CharField(
        max_length=20,
        choices=TipoUsuario.choices,
        default=TipoUsuario.PASSAGEIRO,
        verbose_name=_("Tipo de usuário")
    )

    foto = models.ImageField(
        upload_to="usuarios/",
        blank=True,
        null=True,
        verbose_name=_("Foto")
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Ativo")
    )

    is_staff = models.BooleanField(
        default=False,
        verbose_name=_("Acesso ao Admin")
    )

    date_joined = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Data de cadastro")
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Última atualização")
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.email} ({self.tipo})"

    @property
    def is_passageiro(self):
        return self.tipo == self.TipoUsuario.PASSAGEIRO

    @property
    def is_motorista(self):
        return self.tipo == self.TipoUsuario.MOTORISTA

    @property
    def is_empresa(self):
        return self.tipo == self.TipoUsuario.EMPRESA

    @property
    def is_super_admin(self):
        return self.tipo == self.TipoUsuario.SUPERUSER
