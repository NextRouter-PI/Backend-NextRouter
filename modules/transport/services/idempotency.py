"""Guard compartilhado de idempotência por `operation_id`."""

from collections.abc import Callable

from shared.exceptions import require


def check_idempotent_operation(
    queryset,
    *,
    operation_id,
    matches: Callable[[object], bool],
    conflict_message: str = 'O identificador já foi usado em outra operação.',
):
    """Retorna o evento existente se `operation_id` for replay idêntico, ou levanta conflito."""
    existing = queryset.filter(operation_id=operation_id).first()
    if existing is not None:
        require(matches(existing), 'idempotency_conflict', conflict_message)
    return existing
