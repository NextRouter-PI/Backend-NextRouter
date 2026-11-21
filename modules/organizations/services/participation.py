"""Barreira compartilhada para encerramento e mudança de grupo do domínio novo."""

from modules.organizations.hooks import run_profile_change_guards


def ensure_profile_can_change(profile, *, now):
    """Chamador já bloqueou empresa/perfil; guards de transporte são registrados via `hooks`."""
    run_profile_change_guards(profile, now=now)
