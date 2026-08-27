from django.db import models
from django.utils.translation import gettext_lazy as _

from authenticator.models.user import User


class EmailToken(models.Model):
    class TokenType(models.TextChoices):
        NEW_PASSWORD = 'new-password', _('Nova Senha')
        NEW_USER = 'new-user', _('Novo Usuário')
        NEW_EMAIL = 'new-email', _('Novo Email')

    user = models.ForeignKey(
        User,
        verbose_name=_('Usuário'),
        on_delete=models.CASCADE,
        related_name='tokens',
        null=True,
        blank=True,
    )

    token_hash = models.CharField(
        max_length=255,
        blank=True,
    )

    email = models.EmailField(
        _('Email'),
        max_length=255,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Data de criação'),
    )

    consumed = models.BooleanField(
        default=False,
        verbose_name=_('Consumido'),
        db_index=True,
    )

    token_type = models.CharField(
        max_length=20,
        choices=TokenType.choices,
        default=TokenType.NEW_USER,
        verbose_name=_('Tipo de Token'),
    )

    class Meta:
        verbose_name = _('Email Token')
        verbose_name_plural = _('Email Tokens')
        db_table = 'authenticator_email_token'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.email} - {self.token_type}'
