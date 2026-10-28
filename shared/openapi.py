from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers

ErrorDetailSerializer = inline_serializer(
    name='ErrorDetailResponse',
    fields={
        'detail': serializers.CharField(
            label='Detalhe do erro',
            help_text='Mensagem legível em português descrevendo o motivo da recusa ou falha da operação.',
        ),
    },
)

ValidationErrorSerializer = inline_serializer(
    name='ValidationErrorResponse',
    fields={
        'detail': serializers.CharField(
            required=False,
            label='Mensagem geral de erro',
            help_text='Presente quando o erro se refere à operação como um todo.',
        ),
        'non_field_errors': serializers.ListField(
            child=serializers.CharField(),
            required=False,
            label='Erros gerais de validação',
            help_text='Lista de mensagens de validação que cruzam múltiplos campos.',
        ),
    },
)

PAGE_PARAMETER = OpenApiParameter(
    name='page',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    required=False,
    description='Número da página (iniciando em 1) do conjunto paginado de resultados.',
    examples=[OpenApiExample('Primeira página', value=1)],
)

PAGE_SIZE_PARAMETER = OpenApiParameter(
    name='page_size',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    required=False,
    description='Quantidade de itens por página (padrão: 10, máximo permitido: 100).',
    examples=[OpenApiExample('Padrão (10 itens)', value=10)],
)

PAGINATION_PARAMETERS = [PAGE_PARAMETER, PAGE_SIZE_PARAMETER]

RESP_400_VALIDATION = OpenApiResponse(
    response=ValidationErrorSerializer,
    description='Dados inválidos no corpo ou nos parâmetros da requisição, ou violação de regra de negócio.',
    examples=[
        OpenApiExample(
            'Erro de validação',
            value={'detail': 'Dados inválidos ou regra de negócio violada.'},
            response_only=True,
        ),
    ],
)

RESP_401_UNAUTHORIZED = OpenApiResponse(
    response=ErrorDetailSerializer,
    description=(
        'Não autenticado, token JWT expirado/inválido ou sessão revogada. '
        'Envie o cookie HttpOnly `access_token` ou o cabeçalho `Authorization: Bearer <access>`.'
    ),
    examples=[
        OpenApiExample(
            'Não autenticado',
            value={'detail': 'As credenciais de autenticação não foram fornecidas.'},
            response_only=True,
        ),
    ],
)

RESP_403_FORBIDDEN = OpenApiResponse(
    response=ErrorDetailSerializer,
    description=(
        'Acesso negado: o usuário autenticado não possui o papel exigido, a empresa ainda não foi aprovada '
        'pelo administrador, o recurso pertence a outra empresa/usuário ou a verificação CSRF falhou.'
    ),
    examples=[
        OpenApiExample(
            'Sem permissão',
            value={'detail': 'Você não tem permissão para executar essa ação.'},
            response_only=True,
        ),
    ],
)

RESP_404_NOT_FOUND = OpenApiResponse(
    response=ErrorDetailSerializer,
    description='Recurso não encontrado ou invisível para a organização/papel do usuário autenticado.',
    examples=[
        OpenApiExample(
            'Não encontrado',
            value={'detail': 'Não encontrado.'},
            response_only=True,
        ),
    ],
)

RESP_429_THROTTLED = OpenApiResponse(
    response=ErrorDetailSerializer,
    description='Limite de requisições excedido (rate limit: 30/minuto para login, 60/hora para tokens de e-mail).',
    examples=[
        OpenApiExample(
            'Limite de tentativas excedido',
            value={'detail': 'Request was throttled. Expected available in 60 seconds.'},
            response_only=True,
        ),
    ],
)

RESP_503_UNAVAILABLE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description='Serviço externo temporariamente indisponível (ex.: SMTP ou servidor de roteamento OSRM).',
    examples=[
        OpenApiExample(
            'Serviço indisponível',
            value={'detail': 'Serviço temporariamente indisponível. Tente novamente em instantes.'},
            response_only=True,
        ),
    ],
)


def document_viewset(
    tag,
    singular,
    plural,
    *,
    read,
    create,
    change,
    delete=None,
    read_response=None,
    create_response=None,
    update_response=None,
    public_read=False,
    public_create=False,
    delete_status=204,
    generic_patch=True,
):
    """Documenta as ações CRUD existentes sem mudar serializers, permissões ou respostas inferidas."""
    read_errors = {} if public_read else {401: RESP_401_UNAUTHORIZED}
    create_errors = {} if public_create else {401: RESP_401_UNAUTHORIZED, 403: RESP_403_FORBIDDEN}
    write_errors = {
        400: RESP_400_VALIDATION,
        401: RESP_401_UNAUTHORIZED,
        403: RESP_403_FORBIDDEN,
        404: RESP_404_NOT_FOUND,
    }
    actions = {
        'list': extend_schema(
            tags=[tag],
            summary=f'Liste {plural}',
            description=read,
            responses={200: read_response, **read_errors} if read_response else None,
        ),
        'retrieve': extend_schema(
            tags=[tag],
            summary=f'Consulte {singular}',
            description=read,
            responses={200: read_response, **read_errors, 404: RESP_404_NOT_FOUND} if read_response else None,
        ),
        'create': extend_schema(
            tags=[tag],
            summary=f'Cadastre {singular}',
            description=create,
            responses={201: create_response, 400: RESP_400_VALIDATION, **create_errors} if create_response else None,
        ),
        'update': extend_schema(
            tags=[tag],
            summary=f'Atualize {singular}',
            description=change,
            responses={200: update_response, **write_errors} if update_response else None,
        ),
        'partial_update': extend_schema(
            tags=[tag],
            summary=f'Atualize {singular}',
            description=change,
            responses={200: update_response, **write_errors} if update_response else None,
        ),
        'destroy': extend_schema(
            tags=[tag],
            summary=f'Exclua {singular}',
            description=delete or change,
            responses={delete_status: None, **write_errors} if update_response else None,
        ),
    }
    if not generic_patch:
        actions.pop('partial_update')

    def decorate(view):
        return extend_schema_view(**{name: schema for name, schema in actions.items() if hasattr(view, name)})(view)

    return decorate
