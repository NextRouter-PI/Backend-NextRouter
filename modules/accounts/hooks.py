"""Hooks explícitos de desativação de conta para inversão de dependência sem ciclos.

`pre_locks` executam dentro da transação ANTES de bloquear `User` (preservando a ordem
determinística Company -> User contra deadlocks); `guards` executam DEPOIS de bloquear `User`.
"""

from collections.abc import Callable

AccountHook = Callable[[object], None]

_DEACTIVATION_PRE_LOCKS: list[AccountHook] = []
_DEACTIVATION_GUARDS: list[AccountHook] = []


def register_deactivation_pre_lock(hook: AccountHook) -> None:
    if hook not in _DEACTIVATION_PRE_LOCKS:
        _DEACTIVATION_PRE_LOCKS.append(hook)


def register_deactivation_guard(hook: AccountHook) -> None:
    if hook not in _DEACTIVATION_GUARDS:
        _DEACTIVATION_GUARDS.append(hook)


def run_deactivation_pre_locks(user_id) -> None:
    for hook in _DEACTIVATION_PRE_LOCKS:
        hook(user_id)


def run_deactivation_guards(user_id) -> None:
    for hook in _DEACTIVATION_GUARDS:
        hook(user_id)
