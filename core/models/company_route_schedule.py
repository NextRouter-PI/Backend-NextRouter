from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from core.models.company_route_group import CompanyRouteGroup


class CompanyRouteSchedule(models.Model):
    route_group = models.ForeignKey(
        CompanyRouteGroup,
        on_delete=models.CASCADE,
        verbose_name=_('Grupo de Rota'),
        related_name='schedules',
    )
    go_hour = models.TimeField(null=True, blank=True, verbose_name=_('Hora de ida'))
    return_hour = models.TimeField(null=True, blank=True, verbose_name=_('Hora de retorno'))

    def __str__(self):
        return f'Ida: {self.go_hour} | Volta: {self.return_hour}'


    class Meta:
        verbose_name = _('Horário da Rota')
        verbose_name_plural = _('Horários das Rotas')
        db_table = 'core.company_route_schedule'
        constraints = [
            models.CheckConstraint(condition=Q(return_hour__gt=F('go_hour')), name='return_hour_after_go_hour'),
            models.UniqueConstraint(fields=['return_hour', 'go_hour'], name='unique_return_and_go_hour'),
        ]

