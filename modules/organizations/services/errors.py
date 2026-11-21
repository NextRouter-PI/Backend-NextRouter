from shared.exceptions import DomainError


class MembershipError(DomainError):
    """Erro de domínio com código estável, independente de HTTP/admin."""
