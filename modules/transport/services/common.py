"""Fachada compatível dos utilitários de domínio de transporte."""

from shared.exceptions import DomainError, get, require

from .actors import active_actor, company_actor, driver_actor, membership_for
from .idempotency import check_idempotent_operation
from .locking import lock_company, lock_for_company, lock_travel
from .notifications import notify, travel_recipients

__all__ = [
    'DomainError',
    'active_actor',
    'check_idempotent_operation',
    'company_actor',
    'driver_actor',
    'editable',
    'get',
    'invalidate',
    'lock_company',
    'lock_for_company',
    'lock_travel',
    'membership_for',
    'notify',
    'require',
    'travel_recipients',
]


def editable(travel):
    travel.ensure_editable()


def invalidate(travel):
    travel.invalidate()
