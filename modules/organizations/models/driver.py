from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.accounts.models.user import User
from modules.uploads.models.document import Document


class Driver(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Motorista (Usuário)'),
        related_name='driver',
        unique=True,
    )
    cnh = models.OneToOneField(
        Document,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cnh',
        verbose_name=_('CNH'),
    )
    # Quando o motorista autorizou compartilhar a localização durante as viagens (LGPD).
    # Sem isso o servidor recusa posições; revogar volta para nulo.
    location_consent_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Consentimento de localização em'),
    )

    class Meta:
        verbose_name = _('Motorista')
        verbose_name_plural = _('Motoristas')
        db_table = 'authenticator_driver'
        ordering = ('user__name',)

    def __str__(self):
        user = self._state.fields_cache.get('user')
        if user is not None:
            return user.name.title()
        return f'Motorista #{self.pk}' if self.pk else _('Motorista sem usuário')
