import uuid
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validation import related_values


class TravelParticipation(models.Model):
    travel = models.ForeignKey('router.Travel', on_delete=models.PROTECT, related_name='participations')
    eligibility = models.ForeignKey(
        'router.ServiceDayEligibility', on_delete=models.PROTECT, related_name='participations'
    )
    leg = models.CharField(max_length=8, choices=[('outbound', 'Ida'), ('return', 'Retorno')])
    status = models.CharField(
        max_length=12,
        choices=[
            ('allocated', 'Alocado'),
            ('withdrawn', 'Desistiu'),
            ('no_show', 'Ausente'),
            ('on_board', 'Embarcado'),
            ('dropped_off', 'Desembarcado'),
        ],
        default='allocated',
    )
    allocated_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    no_show_at = models.DateTimeField(null=True, blank=True)
    boarded_at = models.DateTimeField(null=True, blank=True)
    dropped_off_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Participação em viagem'
        verbose_name_plural = 'Participações em viagens'
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['travel', 'eligibility'], name='travel_participant_unique'),
            models.UniqueConstraint(
                fields=['eligibility', 'leg'],
                condition=models.Q(status__in=['allocated', 'on_board', 'dropped_off']),
                name='participant_one_effective_leg',
            ),
            models.CheckConstraint(condition=models.Q(leg__in=['outbound', 'return']), name='participant_leg_valid'),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status='allocated',
                        withdrawn_at__isnull=True,
                        no_show_at__isnull=True,
                        boarded_at__isnull=True,
                        dropped_off_at__isnull=True,
                    )
                    | models.Q(
                        status='withdrawn',
                        withdrawn_at__isnull=False,
                        no_show_at__isnull=True,
                        boarded_at__isnull=True,
                        dropped_off_at__isnull=True,
                    )
                    | models.Q(
                        status='no_show',
                        withdrawn_at__isnull=True,
                        no_show_at__isnull=False,
                        boarded_at__isnull=True,
                        dropped_off_at__isnull=True,
                    )
                    | models.Q(
                        status='on_board',
                        withdrawn_at__isnull=True,
                        no_show_at__isnull=True,
                        boarded_at__isnull=False,
                        dropped_off_at__isnull=True,
                    )
                    | models.Q(
                        status='dropped_off',
                        withdrawn_at__isnull=True,
                        no_show_at__isnull=True,
                        boarded_at__isnull=False,
                        dropped_off_at__isnull=False,
                    )
                ),
                name='participation_status_event_times',
            ),
            *[
                models.CheckConstraint(
                    condition=models.Q(**{f'{field}__isnull': True})
                    | models.Q(**{f'{field}__gte': models.F('allocated_at')}),
                    name=f'participation_{field}_order',
                )
                for field in ('withdrawn_at', 'no_show_at', 'boarded_at', 'dropped_off_at')
            ],
            models.CheckConstraint(
                condition=models.Q(dropped_off_at__isnull=True) | models.Q(dropped_off_at__gte=models.F('boarded_at')),
                name='participation_drop_after_board',
            ),
        ]

    def __str__(self):
        return f'Participação de viagem #{self.pk}'

    def clean(self):
        super().clean()
        travel = related_values(self, 'travel', 'service_day_id', 'service_id', 'service__direction')
        eligibility = related_values(self, 'eligibility', 'day_id', 'authorized_service_ids')
        errors = {}
        if travel and travel['service_day_id'] is None:
            errors['travel'] = 'A participação nova exige uma viagem datada.'
        if travel and eligibility and travel['service_day_id'] != eligibility['day_id']:
            errors['eligibility'] = 'A elegibilidade deve pertencer ao atendimento da viagem.'
        if travel and travel['service__direction'] != self.leg:
            errors['leg'] = 'O trecho deve corresponder ao serviço da viagem.'
        if travel and eligibility and travel['service_id'] not in eligibility['authorized_service_ids']:
            errors['travel'] = 'O serviço da viagem não está autorizado para o passageiro nesse dia.'
        if errors:
            raise ValidationError(errors)


class ParticipationEvent(models.Model):
    participation = models.ForeignKey(TravelParticipation, on_delete=models.PROTECT, related_name='events')
    kind = models.CharField(
        max_length=12,
        choices=[
            ('allocated', 'Alocação'),
            ('withdrawn', 'Desistência'),
            ('no_show', 'Ausência'),
            ('boarded', 'Embarque'),
            ('dropped_off', 'Desembarque'),
            ('correction', 'Correção'),
        ],
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='participation_events')
    occurred_at = models.DateTimeField(default=timezone.now)
    operation_id = models.UUIDField(default=uuid.uuid4, unique=True)
    corrects = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='corrections')
    reason = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = 'Evento de participação'
        verbose_name_plural = 'Eventos de participação'
        constraints: ClassVar[list] = [
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=['allocated', 'withdrawn', 'no_show', 'boarded', 'dropped_off', 'correction']
                ),
                name='participation_event_kind_valid',
            ),
            models.CheckConstraint(
                condition=(models.Q(kind='correction', corrects__isnull=False) & ~models.Q(reason=''))
                | (~models.Q(kind='correction') & models.Q(corrects__isnull=True)),
                name='participation_correction_has_reason',
            ),
            models.CheckConstraint(
                condition=~models.Q(corrects=models.F('pk')), name='participation_no_self_correction'
            ),
        ]

    def __str__(self):
        return f'Evento operacional #{self.pk}'

    def clean(self):
        super().clean()
        corrected = related_values(self, 'corrects', 'participation_id')
        if corrected and corrected['participation_id'] != self.participation_id:
            raise ValidationError({'corrects': 'A correção deve se referir à mesma participação.'})


class SeatReservation(models.Model):
    request = models.ForeignKey('router.DailyChangeRequest', on_delete=models.PROTECT, related_name='seat_reservations')
    travel = models.ForeignKey('router.Travel', on_delete=models.PROTECT, related_name='seat_reservations')
    status = models.CharField(
        max_length=8,
        choices=[('held', 'Reservada'), ('released', 'Liberada'), ('consumed', 'Consumida')],
        default='held',
    )
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Reserva de capacidade'
        verbose_name_plural = 'Reservas de capacidade'
        constraints: ClassVar[list] = [
            models.UniqueConstraint(fields=['request', 'travel'], name='seat_reservation_request_travel'),
            models.UniqueConstraint(
                fields=['request'], condition=models.Q(status='held'), name='seat_one_held_request'
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F('created_at')), name='seat_reservation_expiry'
            ),
            models.CheckConstraint(
                condition=models.Q(status='held', closed_at__isnull=True)
                | models.Q(status__in=['released', 'consumed'], closed_at__isnull=False),
                name='seat_reservation_terminal_audit',
            ),
        ]

    def __str__(self):
        return f'Reserva #{self.pk}'

    def clean(self):
        super().clean()
        travel = related_values(self, 'travel', 'service_id', 'service_day_id')
        request = related_values(self, 'request', 'proposed_service_id', 'response__eligibility__day_id')
        if (
            travel
            and request
            and (
                travel['service_id'] != request['proposed_service_id']
                or travel['service_day_id'] != request['response__eligibility__day_id']
            )
        ):
            raise ValidationError({'travel': 'A reserva deve corresponder ao serviço/data propostos.'})
