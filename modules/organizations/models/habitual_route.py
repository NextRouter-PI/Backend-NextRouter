from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.organizations.models.company_route_group import CompanyRouteGroup


class HabitualRoute(models.Model):
    """Rota habitual (com passageiros no mapa) ou compartilhada (apenas nome) dentro de um grupo."""

    class Kind(models.TextChoices):
        HABITUAL = 'habitual', _('Rota habitual')
        SHARED = 'shared', _('Rota compartilhada')

    route_group = models.ForeignKey(
        CompanyRouteGroup,
        on_delete=models.PROTECT,
        related_name='habitual_routes',
        verbose_name=_('Grupo de atendimento'),
    )
    name = models.CharField(max_length=100, verbose_name=_('Nome da rota'))
    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.HABITUAL,
        db_index=True,
        verbose_name=_('Tipo de rota'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_habitual_routes',
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = _('Rota habitual')
        verbose_name_plural = _('Rotas habituais')
        ordering = ('route_group_id', 'kind', 'name', 'pk')
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=['route_group', 'name'],
                name='unique_group_habitual_route_name',
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=('habitual', 'shared')),
                name='habitual_route_valid_kind',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_kind_display()})'
