from django.core.exceptions import ValidationError


class MembershipError(ValidationError):
    """Erro de domínio com código estável, independente de HTTP/admin."""
