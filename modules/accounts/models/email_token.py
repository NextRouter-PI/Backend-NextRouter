from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import models
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.accounts.models.user import User


class EmailTokenQuerySet(models.QuerySet):
    def unconsumed(self):
        return self.filter(consumed=False)

    def for_lookup(self, *, email: str, token_type: str, user=None):
        qs = self.unconsumed().filter(email__iexact=email, token_type=token_type)
        if token_type == EmailToken.TokenType.NEW_EMAIL:
            qs = qs.filter(user=user)
        return qs.order_by('-created_at')

    def valid_unconsumed(self, *, email: str, token_type: str, user=None, now=None):
        cutoff = (now or timezone.now()) - timedelta(minutes=settings.EMAIL_TOKEN_EXPIRATION_MINUTES)
        return self.for_lookup(email=email, token_type=token_type, user=user).filter(
            created_at__gte=cutoff, failed_attempts__lt=settings.EMAIL_TOKEN_MAX_ATTEMPTS
        )

    def in_cooldown(self, *, email: str, token_type: str, seconds: int | None = None, now=None):
        window = settings.EMAIL_TOKEN_RESEND_SECONDS if seconds is None else seconds
        since = (now or timezone.now()) - timedelta(seconds=window)
        return self.filter(email__iexact=email, token_type=token_type, created_at__gte=since)


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

    failed_attempts = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('Tentativas inválidas'),
    )

    token_type = models.CharField(
        max_length=20,
        choices=TokenType.choices,
        default=TokenType.NEW_USER,
        verbose_name=_('Tipo de Token'),
    )

    objects = EmailTokenQuerySet.as_manager()

    class Meta:
        verbose_name = _('Código de e-mail')
        verbose_name_plural = _('Códigos de e-mail')
        db_table = 'authenticator_email_token'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.email} - {self.token_type}'

    def is_expired(self, *, now=None) -> bool:
        moment = now or timezone.now()
        return moment > self.created_at + timedelta(minutes=settings.EMAIL_TOKEN_EXPIRATION_MINUTES)

    def is_blocked(self) -> bool:
        return self.failed_attempts >= settings.EMAIL_TOKEN_MAX_ATTEMPTS

    def verify_code(self, raw_code: str) -> bool:
        if check_password(raw_code, self.token_hash):
            return True
        EmailToken.objects.filter(pk=self.pk).update(failed_attempts=F('failed_attempts') + 1)
        return False

    def consume_atomically(self) -> bool:
        updated = EmailToken.objects.filter(pk=self.pk, consumed=False).update(consumed=True)
        if updated:
            self.consumed = True
        return bool(updated)
