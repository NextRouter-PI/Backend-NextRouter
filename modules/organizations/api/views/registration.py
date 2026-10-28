from drf_spectacular.utils import OpenApiExample, PolymorphicProxySerializer, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from modules.accounts.api.serializers.user import UserCreateSerializer
from modules.organizations.api.serializers.company import CompanyCreateSerializer
from modules.organizations.api.serializers.driver import DriverCreateSerializer
from modules.organizations.api.serializers.passenger import PassengerCreateSerializer
from shared.openapi import RESP_400_VALIDATION, RESP_429_THROTTLED


class RegistrationConfirmView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'email_tokens'

    @extend_schema(
        tags=['Autenticação'],
        summary='Confirme o cadastro',
        description=(
            'Público. Exige código enviado por e-mail; cria usuário e perfil (aluno, motorista ou empresa). '
            'Empresa e vínculos começam pendentes de aprovação.'
        ),
        request=PolymorphicProxySerializer(
            component_name='RegistrationConfirm',
            resource_type_field_name='type',
            serializers={
                'user': UserCreateSerializer,
                'passenger': PassengerCreateSerializer,
                'driver': DriverCreateSerializer,
                'company': CompanyCreateSerializer,
            },
        ),
        responses={
            201: inline_serializer(
                'RegistrationCreated',
                fields={
                    'detail': serializers.CharField(),
                    'id': serializers.UUIDField(),
                },
            ),
            400: RESP_400_VALIDATION,
            429: RESP_429_THROTTLED,
        },
        examples=[
            OpenApiExample(
                'Cadastro de aluno',
                value={
                    'type': 'passenger',
                    'user_data': {
                        'email': 'aluno@exemplo.com.br',
                        'code': '123456',
                        'password': 'SenhaFicticia!123',
                        'name': 'Aluno Fictício',
                        'cpf': '00000000191',
                    },
                },
                request_only=True,
            ),
            OpenApiExample(
                'Cadastro concluído',
                value={'detail': 'Cadastro concluído.', 'id': '00000000-0000-4000-8000-000000000001'},
                response_only=True,
                status_codes=['201'],
            ),
        ],
    )
    def post(self, request):
        serializers_by_type = {
            'passenger': PassengerCreateSerializer,
            'driver': DriverCreateSerializer,
            'company': CompanyCreateSerializer,
            'user': UserCreateSerializer,
        }
        user_type = request.data.get('type', 'user')
        if user_type not in serializers_by_type:
            return Response({'type': 'Tipo de cadastro inválido.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = serializers_by_type[user_type](data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        user = instance if user_type == 'user' else instance.user
        return Response({'detail': 'Cadastro concluído.', 'id': user.pk}, status=status.HTTP_201_CREATED)
