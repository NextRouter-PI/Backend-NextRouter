from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class MembershipEvent(models.Model):
    """Estrutura de auditoria; gravação e autorização ficarão nos services."""

    class Action(models.TextChoices):
        REQUESTED = 'requested', _('Solicitado')
        APPROVED = 'approved', _('Aprovado')
        REJECTED = 'rejected', _('Recusado')
        WITHDRAWN = 'withdrawn', _('Retirado')
        ENDED = 'ended', _('Encerrado')

    membership = models.ForeignKey('organizations.CompanyMembership', on_delete=models.PROTECT, related_name='events')
    action = models.CharField(max_length=10, choices=Action.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='membership_events')
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    reason = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = _('Evento de vínculo')
        verbose_name_plural = _('Eventos de vínculo')
        ordering = ('occurred_at', 'pk')
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['membership', 'action'], name='membership_event_unique_action'),
            models.CheckConstraint(
                condition=models.Q(action__in=['requested', 'approved', 'rejected', 'withdrawn', 'ended']),
                name='membership_event_valid_action',
            ),
        ]

    def __str__(self):
        return f'Evento #{self.pk} — vínculo #{self.membership_id}'
