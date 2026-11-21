from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.deletion import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.exceptions import ValidationError as InputError
from rest_framework.response import Response
from rest_framework.views import exception_handler

CONFLICT_ERROR_CODES = frozenset({
    'stale_revision',
    'idempotency_conflict',
    'stale_event',
    'membership_open',
    'capacity_exceeded',
    'future_allocation',
    'operation_in_progress',
    'invalid_transition',
})


def _status_for_code(code: str) -> int:
    if code == 'not_found':
        return status.HTTP_404_NOT_FOUND
    if code == 'permission_denied':
        return status.HTTP_403_FORBIDDEN
    if code in CONFLICT_ERROR_CODES:
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


class DomainError(DjangoValidationError):
    """Erro de domínio com código estável e status HTTP associado."""

    default_status_code: int | None = None
    default_code = 'validation_error'

    def __init__(self, message, code=None, params=None, *, status_code=None):
        resolved_code = code or self.default_code
        self.status_code = status_code or self.default_status_code or _status_for_code(resolved_code)
        super().__init__(message, code=resolved_code, params=params)


class ValidationDomainError(DomainError):
    default_status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'validation_error'


class PermissionDomainError(DomainError):
    default_status_code = status.HTTP_403_FORBIDDEN
    default_code = 'permission_denied'


class NotFoundDomainError(DomainError):
    default_status_code = status.HTTP_404_NOT_FOUND
    default_code = 'not_found'


class ConflictDomainError(DomainError):
    default_status_code = status.HTTP_409_CONFLICT
    default_code = 'conflict'


_ERROR_CLASS_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: ValidationDomainError,
    status.HTTP_403_FORBIDDEN: PermissionDomainError,
    status.HTTP_404_NOT_FOUND: NotFoundDomainError,
    status.HTTP_409_CONFLICT: ConflictDomainError,
}


def require(condition, code: str, message: str) -> None:
    if condition:
        return
    error_class = _ERROR_CLASS_BY_STATUS[_status_for_code(code)]
    raise error_class(message, code=code)


def get_or_not_found(queryset, **lookup):
    try:
        return queryset.get(**lookup)
    except queryset.model.DoesNotExist as exc:
        raise NotFoundDomainError('Recurso não encontrado.', code='not_found') from exc


get = get_or_not_found


def custom_exception_handler(exc, context):
    """
    Padroniza erros de domínio (`DomainError` / `DjangoValidationError`), validação de
    `DomainViewSet` e exclusões protegidas (`ProtectedError` / `RestrictedError`).
    """
    if isinstance(exc, InputError):
        from shared.domain_api import DomainViewSet

        if isinstance(context.get('view'), DomainViewSet):
            return Response({'code': 'invalid_input', 'detail': 'Dados inválidos.', 'errors': exc.detail}, status=400)
    if isinstance(exc, DjangoValidationError):
        code = getattr(exc, 'code', None) or 'validation_error'
        status_code = getattr(exc, 'status_code', None) or _status_for_code(code)
        data = {'code': code, 'detail': ' '.join(exc.messages)}
        if hasattr(exc, 'message_dict'):
            data['errors'] = exc.message_dict
        return Response(data, status=status_code)
    if isinstance(exc, ProtectedError | RestrictedError):
        return Response(
            {
                'detail': (
                    'Não é possível excluir este registro pois ainda existem outros dados vinculados a ele. '
                    'Remova ou desvincule esses dados antes de excluí-lo.'
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    return exception_handler(exc, context)
