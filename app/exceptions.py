from django.db.models.deletion import ProtectedError, RestrictedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Converte a tentativa de excluir um registro que ainda é referenciado por outros
    (on_delete=PROTECT/RESTRICT) em um erro 400 legível, em vez de um erro 500.
    """
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
