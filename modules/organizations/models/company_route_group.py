from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.organizations.models.company import Company


class CompanyRouteGroupQuerySet(models.QuerySet):
    def served_cities(self, *, state: str | None = None) -> list[dict[str, str]]:
        qs = (
            self
            .filter(
                company__is_approved=True,
                company__is_rejected=False,
                company__user__is_active=True,
                destination__isnull=False,
            )
            .exclude(destination__city='')
            .exclude(destination__state='')
        )
        if state:
            qs = qs.filter(destination__state__iexact=state.strip())
        seen: set[tuple[str, str]] = set()
        results: list[dict[str, str]] = []
        for city, st in qs.values_list('destination__city', 'destination__state').order_by(
            'destination__state', 'destination__city'
        ):
            clean_city = city.strip()
            clean_state = st.strip().upper()
            key = (clean_city.casefold(), clean_state)
            if clean_city and clean_state and key not in seen:
                seen.add(key)
                results.append({'city': clean_city, 'state': clean_state})
        return results


class CompanyRouteGroup(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        verbose_name=_('Empresa'),
        related_name='route_groups',
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_('Nome do Grupo'),
    )

    destination = models.ForeignKey(
        'organizations.OperationalPoint',
        on_delete=models.PROTECT,
        related_name='destination_groups',
        null=True,
        blank=True,
        verbose_name=_('Destino operacional'),
    )

    objects = CompanyRouteGroupQuerySet.as_manager()

    class Meta:
        verbose_name = _('Grupo de Rota')
        verbose_name_plural = _('Grupos de Rotas')
        db_table = 'authenticator_company_route_group'
        constraints = (models.UniqueConstraint(fields=['company', 'name'], name='unique_company_route_name'),)
        ordering = (
            'company',
            'name',
        )

    def __str__(self):
        company = self._state.fields_cache.get('company')
        label = company.trade_name if company is not None else f'empresa #{self.company_id}'
        return f'{self.name.title()} ({label})'

    def clean(self):
        super().clean()
        if self.destination_id and self.company_id:
            from .operational_point import OperationalPoint

            try:
                destination_id = OperationalPoint._meta.pk.to_python(self.destination_id)
            except ValidationError:
                return  # clean_fields já reporta o ID malformado.
            point = OperationalPoint.objects.filter(pk=destination_id).values('company_id', 'point_type').first()
            if point is not None and point['company_id'] != self.company_id:
                raise ValidationError(_('O destino operacional deve pertencer à empresa do grupo.'))
            if point is not None and point['point_type'] != OperationalPoint.PointType.DESTINATION:
                raise ValidationError(_('O destino do grupo deve ser um ponto operacional do tipo destino.'))
