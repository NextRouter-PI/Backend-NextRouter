from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.geocoding import GeocodingError, lookup_cep_brasilapi


class CepLookupView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        tags=['Autenticação'],
        summary='Consulte endereço e coordenadas por CEP (BrasilAPI v2)',
        description=(
            'Proxy de mesma origem para consulta de CEP via BrasilAPI v2, '
            'retornando endereço e coordenadas quando disponíveis.'
        ),
        responses={
            200: inline_serializer(
                'CepLookupResponse',
                fields={
                    'cep': serializers.CharField(),
                    'state': serializers.CharField(),
                    'city': serializers.CharField(),
                    'neighborhood': serializers.CharField(),
                    'street': serializers.CharField(),
                    'latitude': serializers.FloatField(allow_null=True),
                    'longitude': serializers.FloatField(allow_null=True),
                },
            )
        },
    )
    def get(self, request, cep):
        clean_cep = ''.join(ch for ch in str(cep or '') if ch.isdigit())
        if len(clean_cep) != 8:
            return Response(
                {'detail': 'CEP inválido. Informe 8 dígitos numéricos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = lookup_cep_brasilapi(clean_cep, raise_on_error=True)
        except GeocodingError:
            return Response(
                {'detail': 'Serviço de consulta de CEP temporariamente indisponível.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if data is None:
            return Response(
                {'detail': 'CEP não encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(data)
