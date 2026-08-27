from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.permissions import IsCompanyOwner


# TODO - Enviar email quando aprovado
class ApproveProfileMixin:
    @extend_schema(
        request=None,
        summary='Aprova registro na empresa.',
        description='Esta ação é definitiva e não pode ser desfeita.',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                },
            },
            401: None,
            403: None,
            404: None,
        },
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsCompanyOwner])
    def approve(self, request, pk=None):
        instance = self.get_object()
        instance.is_approved = True
        instance.save(update_fields=['is_approved'])

        return Response(
            {
                'message': 'Aprovado com sucesso.',
            },
            status=status.HTTP_200_OK,
        )
