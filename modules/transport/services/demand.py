"""Respostas diárias de demanda e desistência de trechos pelos passageiros."""

from django.db import transaction
from django.utils import timezone

from modules.organizations.models import CompanyMembership
from modules.transport.models import DailyResponse, ParticipationEvent, RecurringService, ServiceDayEligibility
from shared.exceptions import get, require

from .actors import active_actor
from .locking import lock_for_company
from .notifications import notify, travel_recipients


def eligibility_access(eligibility_id, actor_id, *, company_only=False, allow_closed_membership=False):
    company, eligibility = lock_for_company(
        ServiceDayEligibility.objects.all(),
        eligibility_id,
        company_getter=lambda item: item.day.route_group.company_id,
        company_filter='day__route_group__company',
    )
    actor = active_actor(actor_id)
    expected_actor = company.user_id if company_only else eligibility.passenger.user_id
    require(actor.pk == expected_actor, 'permission_denied', 'Acesso não autorizado à resposta diária.')
    if not allow_closed_membership:
        require(company.is_operational, 'company_unavailable', 'Empresa indisponível.')
        participation = eligibility.group_membership
        require(
            participation.ended_at is None
            and participation.membership.status == 'active'
            and participation.membership.company_id == company.pk
            and eligibility.passenger.user.is_active,
            'membership_unavailable',
            'O vínculo/grupo não está vigente.',
        )
        require(
            CompanyMembership.objects.filter(
                pk=participation.membership_id, passenger_id=eligibility.passenger_id, company=company, status='active'
            ).exists(),
            'membership_unavailable',
            'A elegibilidade não corresponde ao vínculo.',
        )
    return company, eligibility


def selected_service(eligibility, service_id, leg):
    if service_id is None:
        return None
    require(
        type(service_id) is int and eligibility.authorizes(service_id),
        'service_not_authorized',
        'O serviço não está autorizado nesse atendimento.',
    )
    return get(
        RecurringService.objects.filter(route_group_id=eligibility.day.route_group_id, direction=leg), pk=service_id
    )


@transaction.atomic
def answer_day(*, actor_id, eligibility_id, outbound_service_id, return_service_id, expected_revision):
    _, eligibility = eligibility_access(eligibility_id, actor_id)
    day, now = eligibility.day, timezone.now()
    require(not day.canceled_at, 'day_canceled', 'O atendimento está cancelado.')
    require(
        day.is_normal_window_open(now=now),
        'response_window_closed',
        'A janela normal de respostas está fechada.',
    )
    response = DailyResponse.objects.filter(eligibility=eligibility).first()
    require(expected_revision == (response.revision if response else 0), 'stale_revision', 'A resposta foi alterada.')
    outbound = selected_service(eligibility, outbound_service_id, 'outbound')
    returning = selected_service(eligibility, return_service_id, 'return')
    require(
        not day.has_started_execution(),
        'execution_started',
        'A execução deste atendimento já começou.',
    )
    if (
        response
        and response.outbound_service_id == outbound_service_id
        and response.return_service_id == return_service_id
        and not response.outbound_withdrawn_at
        and not response.return_withdrawn_at
    ):
        return response
    response = response or DailyResponse(eligibility=eligibility, revision=0)
    response.outbound_service, response.return_service = outbound, returning
    response.outbound_withdrawn_at = response.return_withdrawn_at = None
    response.answered_at = now
    response.revision += 1
    response.full_clean()
    response.save()
    for travel in day.travels.filter(status='scheduled').order_by('pk'):
        travel.invalidate()
    return response


@transaction.atomic
def withdraw_leg(*, actor_id, eligibility_id, leg):
    _, eligibility = eligibility_access(eligibility_id, actor_id, allow_closed_membership=True)
    require(leg in ('outbound', 'return'), 'invalid_leg', 'Trecho inválido.')
    response = get(DailyResponse.objects.select_for_update(), eligibility=eligibility)
    pending = list(response.change_requests.open_requests().filter(leg=leg))
    if not response.has_active_choice(leg):
        require(
            response.service_id_for(leg) is not None or pending or response.change_requests.filter(leg=leg).exists(),
            'no_choice',
            'Não há escolha ou pedido para este trecho.',
        )
        now = timezone.now()
        for request in pending:
            request.supersede(now=now)
            notify(
                recipients=[eligibility.day.route_group.company.user_id],
                kind='request',
                resource_type='request',
                resource_id=request.pk,
                key=f'request:{request.pk}:superseded',
                status='superseded',
            )
        return response
    participants = list(
        eligibility.participations.filter(leg=leg).exclude(travel__status='canceled').order_by('travel_id', 'pk')
    )
    require(
        not any(participant.status in ('on_board', 'dropped_off') for participant in participants),
        'already_boarded',
        'Não é permitido desistir depois do embarque.',
    )
    now = timezone.now()
    response.withdraw_leg(leg, now=now)
    response.save(update_fields=[f'{leg}_withdrawn_at', 'revision'])
    for request in pending:
        request.supersede(now=now)
    for participant in participants:
        if participant.status != 'allocated':
            continue
        participant.status = 'withdrawn'
        participant.withdrawn_at = now
        participant.save(update_fields=['status', 'withdrawn_at'])
        ParticipationEvent.objects.create(
            participation=participant, kind='withdrawn', actor_id=actor_id, occurred_at=now
        )
        travel = participant.travel
        if travel.status == 'scheduled':
            travel.invalidate()
        notify(
            recipients=travel_recipients(travel),
            kind='operation',
            resource_type='travel',
            resource_id=travel.pk,
            key=f'withdrawal:{participant.pk}:{response.revision}',
            status='withdrawn',
        )
    return response
