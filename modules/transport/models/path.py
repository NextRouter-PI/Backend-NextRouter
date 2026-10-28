from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.organizations.models.company_route_group import CompanyRouteGroup


class Path(models.Model):
    points = models.JSONField(default=list, blank=True, verbose_name=_('Pontos de Parada'))
    start_point = models.JSONField(null=True, blank=True)
    end_point = models.JSONField(null=True, blank=True)
    distance_meters = models.FloatField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    geometry = models.JSONField(null=True, blank=True)
    is_outdated = models.BooleanField(default=True)
    optimized_at = models.DateTimeField(null=True, blank=True)

    route_group = models.ForeignKey(
        CompanyRouteGroup,
        verbose_name=_('Grupo de Rotas'),
        related_name='paths',
        on_delete=models.CASCADE,
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_('Nome da Rota'),
    )

    class Meta:
        verbose_name = _('Rota')
        verbose_name_plural = _('Rotas')
        db_table = 'router_path'
        ordering = (
            'route_group',
            'name',
        )

    def __str__(self):
        return f'{self.name.title()} ({self.route_group.name.title()})'

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if self.pk and (update_fields is None or 'points' in update_fields or 'route_group' in update_fields):
            previous = type(self).objects.filter(pk=self.pk).values('points', 'route_group_id').first()
            if (
                previous
                and (previous['points'] != self.points or previous['route_group_id'] != self.route_group_id)
                and (update_fields is None or 'is_outdated' not in update_fields)
            ):
                self.is_outdated = True
                if update_fields is not None:
                    kwargs['update_fields'] = {*update_fields, 'is_outdated'}
        return super().save(*args, **kwargs)
