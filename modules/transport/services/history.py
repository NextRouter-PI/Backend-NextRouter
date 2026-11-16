from django.db import transaction
from django.utils import timezone

from modules.organizations.models import CompanyMembership
from modules.transport.models import DriverRating, LostItem, LostItemEvent

from .common import active_actor, company_actor, get, lock_travel, require


def completed_passenger(travel, actor_id):
    return travel.participations.filter(
        eligibility__passenger__user_id=actor_id,
        status='dropped_off',
        dropped_off_at__isnull=False,
        eligibility__group_membership__membership__status='active',
    ).exists()


def history_actor(travel, actor_id):
    active_actor(actor_id)
    require(
        travel.company.is_approved and not travel.company.is_rejected and travel.company.user.is_active,
        'company_unavailable',
        'A empresa está indisponível.',
    )
    require(travel.status == 'finished', 'travel_not_finished', 'A viagem precisa estar finalizada.')
    driver = (
        travel.driver_id
        and travel.driver.user_id == actor_id
        and CompanyMembership.objects.filter(
            company_id=travel.company_id, driver_id=travel.driver_id, status='active'
        ).exists()
    )
    passenger = completed_passenger(travel, actor_id)
    require(driver or passenger, 'permission_denied', 'É necessário ter participado da viagem e manter vínculo ativo.')
    return bool(passenger)


@transaction.atomic
def rate_driver(*, actor_id, travel_id, score, comment=''):
    _, travel = lock_travel(travel_id)
    require(history_actor(travel, actor_id), 'permission_denied', 'Somente aluno desembarcado pode avaliar.')
    require(type(score) is int and 1 <= score <= 5, 'invalid_score', 'A nota deve estar entre 1 e 5.')
    require(isinstance(comment, str) and len(comment) <= 500, 'invalid_comment', 'Comentário inválido.')
    existing = DriverRating.objects.filter(travel=travel, passenger_id=actor_id, driver_id=travel.driver_id).first()
    if existing:
        require(existing.score == score and existing.comment == comment, 'rating_exists', 'A viagem já foi avaliada.')
        return existing
    return DriverRating.objects.create(
        travel=travel, passenger_id=actor_id, driver=travel.driver, score=score, comment=comment
    )


@transaction.atomic
def report_lost_item(*, actor_id, travel_id, item_description, operation_id):
    _, travel = lock_travel(travel_id)
    history_actor(travel, actor_id)
    require(
        isinstance(item_description, str) and 0 < len(item_description.strip()) <= 255,
        'invalid_description',
        'Informe uma descrição de até 255 caracteres.',
    )
    old = LostItemEvent.objects.filter(operation_id=operation_id).select_related('item').first()
    if old:
        require(
            old.actor_id == actor_id
            and old.item.travel_id == travel.pk
            and old.status == 'reported'
            and old.item.item_description == item_description.strip(),
            'idempotency_conflict',
            'O identificador já foi utilizado.',
        )
        return old.item
    item = LostItem.objects.create(travel=travel, user_id=actor_id, item_description=item_description.strip())
    LostItemEvent.objects.create(
        item=item, status='reported', actor_id=actor_id, operation_id=operation_id, occurred_at=timezone.now()
    )
    return item


@transaction.atomic
def transition_lost_item(*, actor_id, item_id, target_status, operation_id):
    initial = get(LostItem.objects.all(), pk=item_id)
    company, travel = lock_travel(initial.travel_id)
    company_actor(company, actor_id)
    item = get(LostItem.objects.select_for_update().filter(travel=travel), pk=item_id)
    old = LostItemEvent.objects.filter(operation_id=operation_id).first()
    if old:
        require(
            old.item_id == item.pk and old.actor_id == actor_id and old.status == target_status,
            'idempotency_conflict',
            'O identificador já foi utilizado.',
        )
        return item
    require(
        (item.status, target_status) in [('reported', 'found'), ('found', 'returned')],
        'invalid_transition',
        'Transição de custódia inválida; não é permitida reabertura.',
    )
    LostItemEvent.objects.create(
        item=item, status=target_status, actor_id=actor_id, operation_id=operation_id, occurred_at=timezone.now()
    )
    item.status = target_status
    item.save(update_fields=['status'])
    return item
