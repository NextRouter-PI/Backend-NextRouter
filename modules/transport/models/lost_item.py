import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.accounts.models.user import User
from modules.transport.models.travel import Travel
from shared.exceptions import require


class LostItem(models.Model):
    class Status(models.TextChoices):
        REPORTED = 'reported', _('Relatado')
        FOUND = 'found', _('Encontrado')
        RETURNED = 'returned', _('Devolvido')

    ALLOWED_TRANSITIONS: ClassVar[dict[str, str]] = {
        Status.REPORTED: Status.FOUND,
        Status.FOUND: Status.RETURNED,
    }

    travel = models.ForeignKey(
        Travel,
        on_delete=models.PROTECT,
        verbose_name=_('Viagem'),
        related_name='lost_items',
    )

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('Usuário'),
        related_name='lost_items',
    )

    item_description = models.CharField(
        max_length=255,
        verbose_name=_('Descrição do item'),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REPORTED,
        verbose_name=_('Status'),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Data de registro'),
    )

    class Meta:
        verbose_name = _('Item Perdido')
        verbose_name_plural = _('Itens Perdidos')
        db_table = 'router_lost_item'
        ordering = ('-created_at',)

    def __str__(self):
        user = self._state.fields_cache.get('user')
        owner = user.name if user is not None else f'usuário #{self.user_id}'
        return f'{self.item_description[:30]} - {owner}'

    def transition_to(self, target_status: str) -> None:
        expected = self.ALLOWED_TRANSITIONS.get(self.status)
        require(expected == target_status, 'invalid_transition', 'Transição de custódia inválida.')
        self.status = target_status
        self.save(update_fields=['status'])


class LostItemEvent(models.Model):
    item = models.ForeignKey(LostItem, on_delete=models.PROTECT, related_name='events')
    status = models.CharField(max_length=20, choices=LostItem.Status.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='lost_item_events')
    occurred_at = models.DateTimeField(default=timezone.now)
    operation_id = models.UUIDField(default=uuid.uuid4, unique=True)

    class Meta:
        ordering = ('occurred_at', 'pk')
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(status__in=['reported', 'found', 'returned']), name='lost_item_event_status_valid'
            ),
            models.UniqueConstraint(fields=['item', 'status'], name='lost_item_one_event_per_status'),
        ]

    def __str__(self):
        return f'Evento de custódia #{self.pk}'
