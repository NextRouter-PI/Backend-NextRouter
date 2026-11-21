"""Hooks explícitos de moderação de empresa para inversão de dependência sem ciclos."""

from collections.abc import Callable

CompanyModerationGuard = Callable[[object, bool], None]

_COMPANY_MODERATION_GUARDS: list[CompanyModerationGuard] = []


def register_company_moderation_guard(guard: CompanyModerationGuard) -> None:
    if guard not in _COMPANY_MODERATION_GUARDS:
        _COMPANY_MODERATION_GUARDS.append(guard)


def run_company_moderation_guards(company, *, approve: bool) -> None:
    for guard in _COMPANY_MODERATION_GUARDS:
        guard(company, approve)
