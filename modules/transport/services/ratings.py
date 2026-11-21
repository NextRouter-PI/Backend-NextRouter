"""Avaliações de motoristas e checagem de participação concluída."""

from django.db import transaction

from modules.organizations.models import CompanyMembership
from modules.transport.models import DriverRating, Travel
from shared.exceptions import require

from .actors import active_actor
from .locking import lock_travel


def completed_passenger(travel, actor_id) -> bool:
    return travel.participations.filter(
        eligibility__passenger__user_id=actor_id,
        status='dropped_off',
        dropped_off_at__isnull=False,
        eligibility__group_membership__membership__status='active',
    ).exists()


def history_actor(travel, actor_id) -> bool:
    active_actor(actor_id)
    require(
        travel.company.is_operational,
        'company_unavailable',
        'A empresa está indisponível.',
    )
    require(travel.status == Travel.Status.FINISHED, 'travel_not_finished', 'A viagem precisa estar finalizada.')
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
