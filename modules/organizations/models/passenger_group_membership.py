from datetime import datetime
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .company_membership import CompanyMembership
from .company_route_group import CompanyRouteGroup
from .operational_point import OperationalPoint


def _related_values(model, pk, *fields):
    # full_clean chama clean mesmo quando um ID já falhou em clean_fields.
    try:
        pk = model._meta.pk.to_python(pk)
    except ValidationError:
        return None
    return model.objects.filter(pk=pk).values(*fields).first() if pk is not None else None


class PassengerGroupMembership(models.Model):
    """Histórico de participação; ainda não autoriza acesso nem substitui o legado."""

    membership = models.ForeignKey(
        CompanyMembership, on_delete=models.PROTECT, related_name='passenger_group_memberships'
    )
    route_group = models.ForeignKey(CompanyRouteGroup, on_delete=models.PROTECT, related_name='passenger_memberships')
    transport_point = models.ForeignKey(
        OperationalPoint,
        on_delete=models.PROTECT,
        related_name='passenger_memberships',
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(default=timezone.now)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='assigned_passenger_groups'
    )
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='ended_passenger_groups',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _('Participação do aluno no grupo')
        verbose_name_plural = _('Participações dos alunos nos grupos')
        ordering = ('-started_at', '-pk')
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=['membership'],
                condition=models.Q(ended_at__isnull=True),
                name='passenger_group_one_open_membership',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(ended_at__isnull=True, ended_by__isnull=True)
                    | models.Q(ended_at__isnull=False, ended_by__isnull=False)
                ),
                name='passenger_group_end_has_actor',
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F('started_at')),
                name='passenger_group_end_after_start',
            ),
        ]

    def __str__(self):
        return f'Participação #{self.pk} — grupo #{self.route_group_id}'

    def clean(self):
        super().clean()
        errors = {}
        valid_dates = True
        for field in ('started_at', 'ended_at'):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, datetime) or not timezone.is_aware(value)):
                errors[field] = _('Informe um instante completo com fuso horário.')
                valid_dates = False

        membership = _related_values(
            CompanyMembership, self.membership_id, 'company_id', 'passenger_id', 'status', 'reviewed_at', 'ended_at'
        )
        group = _related_values(CompanyRouteGroup, self.route_group_id, 'company_id')
        point = _related_values(OperationalPoint, self.transport_point_id, 'company_id')
        group_company = group['company_id'] if group else None
        point_company = point['company_id'] if point else None
        if membership:
            if membership['passenger_id'] is None:
                errors['membership'] = _('A participação exige um vínculo de passageiro.')
            elif membership['status'] not in (CompanyMembership.Status.ACTIVE, CompanyMembership.Status.ENDED):
                errors['membership'] = _('O vínculo não possui aprovação empresarial.')
            elif membership['status'] == CompanyMembership.Status.ENDED and self.ended_at is None:
                errors['membership'] = _('Um vínculo encerrado não pode manter participação vigente.')
            if group_company is not None and group_company != membership['company_id']:
                errors['route_group'] = _('O grupo deve pertencer à empresa do vínculo.')
            if point_company is not None and point_company != membership['company_id']:
                errors['transport_point'] = _('O ponto deve pertencer à empresa do vínculo.')
            if valid_dates:
                if self.started_at and membership['reviewed_at'] and self.started_at < membership['reviewed_at']:
                    errors['started_at'] = _('A participação não pode começar antes da aprovação empresarial.')
                if self.ended_at and membership['ended_at'] and self.ended_at > membership['ended_at']:
                    errors['ended_at'] = _('A participação não pode terminar depois do vínculo empresarial.')
        if group_company is not None and point_company is not None and group_company != point_company:
            errors['transport_point'] = _('O ponto deve pertencer à empresa do grupo.')
        if errors:
            raise ValidationError(errors)
