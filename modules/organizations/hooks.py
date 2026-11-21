"""Hooks explícitos de organizações para inversão de dependência sem ciclos com `transport`."""

from collections.abc import Callable

CompanyModerationGuard = Callable[[object, bool], None]
ProfileChangeGuard = Callable[[object, object], None]
MembershipNotifier = Callable[..., None]
RouteGroupChangeListener = Callable[[object], None]
AuthorizationCloner = Callable[..., None]

_COMPANY_MODERATION_GUARDS: list[CompanyModerationGuard] = []
_PROFILE_CHANGE_GUARDS: list[ProfileChangeGuard] = []
_MEMBERSHIP_NOTIFIERS: list[MembershipNotifier] = []
_ROUTE_GROUP_CHANGE_LISTENERS: list[RouteGroupChangeListener] = []
_AUTHORIZATION_CLONERS: list[AuthorizationCloner] = []


def register_company_moderation_guard(guard: CompanyModerationGuard) -> None:
    if guard not in _COMPANY_MODERATION_GUARDS:
        _COMPANY_MODERATION_GUARDS.append(guard)


def run_company_moderation_guards(company, *, approve: bool) -> None:
    for guard in _COMPANY_MODERATION_GUARDS:
        guard(company, approve)


def register_profile_change_guard(guard: ProfileChangeGuard) -> None:
    if guard not in _PROFILE_CHANGE_GUARDS:
        _PROFILE_CHANGE_GUARDS.append(guard)


def run_profile_change_guards(profile, *, now) -> None:
    for guard in _PROFILE_CHANGE_GUARDS:
        guard(profile, now)


def register_membership_notifier(notifier: MembershipNotifier) -> None:
    if notifier not in _MEMBERSHIP_NOTIFIERS:
        _MEMBERSHIP_NOTIFIERS.append(notifier)


def emit_membership_notification(*, recipient_id, membership_id, deduplication_key: str, status: str, occurred_at):
    for notifier in _MEMBERSHIP_NOTIFIERS:
        notifier(
            recipient_id=recipient_id,
            membership_id=membership_id,
            deduplication_key=deduplication_key,
            status=status,
            occurred_at=occurred_at,
        )


def register_route_group_change_listener(listener: RouteGroupChangeListener) -> None:
    if listener not in _ROUTE_GROUP_CHANGE_LISTENERS:
        _ROUTE_GROUP_CHANGE_LISTENERS.append(listener)


def notify_route_group_changed(group) -> None:
    for listener in _ROUTE_GROUP_CHANGE_LISTENERS:
        listener(group)


def register_authorization_cloner(cloner: AuthorizationCloner) -> None:
    if cloner not in _AUTHORIZATION_CLONERS:
        _AUTHORIZATION_CLONERS.append(cloner)


def clone_group_service_authorizations(*, source_participation, target_participation, group) -> None:
    for cloner in _AUTHORIZATION_CLONERS:
        cloner(source_participation=source_participation, target_participation=target_participation, group=group)
