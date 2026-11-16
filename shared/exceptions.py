from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.deletion import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.exceptions import ValidationError as InputError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Converte a tentativa de excluir um registro que ainda é referenciado por outros
    (on_delete=PROTECT/RESTRICT) em um erro 400 legível, em vez de um erro 500.
    """
    if isinstance(exc, InputError):
        from shared.domain_api import DomainViewSet

        if isinstance(context.get('view'), DomainViewSet):
            return Response({'code': 'invalid_input', 'detail': 'Dados inválidos.', 'errors': exc.detail}, status=400)
    if isinstance(exc, DjangoValidationError):
        code = getattr(exc, 'code', None) or 'validation_error'
        status_code = 404 if code == 'not_found' else 403 if code == 'permission_denied' else 400
        if code in {
            'stale_revision',
            'idempotency_conflict',
            'stale_event',
            'membership_open',
            'capacity_exceeded',
            'future_allocation',
            'operation_in_progress',
            'invalid_transition',
        }:
            status_code = 409
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
