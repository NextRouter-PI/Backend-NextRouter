# Convenções observadas (não confundir com recomendações universais)

## Padrões reais
- Views DRF separam serializer/permissão por `self.action`; exemplo: `modules/transport/api/views/path.py::PathViewSet.get_serializer_class` e `modules/transport/api/views/path.py::PathViewSet.get_permissions`. **Atenção:** actions também precisam filtrar `get_queryset`; permissão de objeto sozinha não protege listas.
- Validação de relações com empresa/membro em `modules/transport/api/serializers/ownership.py::validate_route_group_ownership` / `modules/transport/api/serializers/ownership.py::validate_driver_in_route_group`; exemplo de uso: `modules/transport/api/serializers/travel.py::TravelCreateSerializer.validate`.
- Persistência multi-modelo em `@transaction.atomic`; lock de motorista/veículo/viagem em `modules/transport/api/views/travel.py::TravelViewSet.start`; efeito externo pós-commit em `modules/transport/services.py::save_travel_location`. Não pressuponha que SQLite reproduz locks de PostgreSQL.
- Exceções DRF padrão geram erros por campo/`non_field_errors`; regras de domínio retornam `{'detail': ...}` e ações às vezes `{'message': ...}`; `shared/exceptions.py::custom_exception_handler` converte exclusão protegida em 400. Não padronize respostas quebrando clientes.
- Paginação por página, `page_size` máximo 100 e resposta `{page,page_size,total_pages,results}` em `shared/pagination.py::CustomPagination`. Filtros `django-filter` por `filterset_fields` ou `filterset_class` em `modules/transport/api/views/travel.py::TravelViewSet` / `modules/organizations/api/views/company.py::CompanyViewSet`.
- Use `filterset_fields` sobre o `get_queryset` já limitado por usuário; `DjangoFilterBackend` é global em `app/settings/base.py::REST_FRAMEWORK`. `started_at__date` filtra viagens iniciadas por data local (`modules/transport/api/views/travel.py::TravelViewSet`); nunca filtre antes de aplicar isolamento (`modules/organizations/api/views/passenger.py::PassengerViewSet.get_queryset`).
- API usa URLs em inglês (`modules/transport/urls.py::router`), mensagens em português (`modules/transport/api/views/travel.py::TravelViewSet._change_status`), fuso `America/Sao_Paulo` com `USE_TZ=True` (`app/settings/base.py::TIME_ZONE`).
- Esquema OpenAPI usa `DEFAULT_SCHEMA_CLASS` (`app/settings/base.py::REST_FRAMEWORK`). Em ViewSet CRUD, anote `@document_viewset` com tag, papéis/regras e serializers de saída; ele aplica `@extend_schema_view` e erros comuns sem mudar respostas reais (`shared/openapi.py::document_viewset`, `modules/transport/api/views/vehicle.py::VehicleViewSet`). Em actions/APIViews, use `@extend_schema` com tag, summary imperativo, descrição de papel/efeito, request, respostas reais por status e exemplos fictícios (`modules/transport/api/views/path.py::PathViewSet.optimize`, `modules/organizations/api/views/registration.py::RegistrationConfirmView.post`). Não invente status nem copie PII; parâmetros manuais de query exigem `OpenApiParameter` (os filtros `django-filter` já são inferidos em `app/settings/base.py::REST_FRAMEWORK`).

## Endpoint novo: checklist
1. Decida se cabe em ViewSet existente; proteja `get_queryset`, `get_permissions` e regras por objeto (exemplo `modules/transport/api/views/path.py::PathViewSet`).
2. Defina serializer de entrada/saída sem aceitar silenciosamente campos vedados; valide ownership no serializer se relacionar IDs (`modules/transport/api/serializers/travel.py::TravelCreateSerializer`).
3. Registre rota em `modules/transport/urls.py::router` ou `modules/accounts/urls.py::urlpatterns`; agregação em `app/api.py::router` (não duplique prefixo `api/`).
4. Anote toda ação nova com tag, summary, descrição do papel/efeitos, request, respostas por status e exemplo fictício, usando `@extend_schema` (`modules/transport/api/views/travel.py::TravelViewSet.start`); gere schema com `--validate --fail-on-warn` conforme [comandos](../AGENTS.md).
5. Teste acesso de outra empresa, não aprovado, owner e conflito; use `tests/helpers.py::BaseAPITestCase`; consulte baseline em [PROGRESSO](PROGRESSO.md).
6. Se contrato mudar, combine compatibilidade aditiva/versionada com dono e atualize documentação no mesmo commit (`app/api.py::router`, [DECISOES](DECISOES.md)).

## Model/migration
1. Use `settings.AUTH_USER_MODEL` nas novas FK de usuário (`modules/accounts/models/user_session.py::UserSession`), preserve nomes de tabela/constraints existentes (`modules/transport/models/travel.py::Travel.Meta`).
2. Antes de criar/aplicar migration pergunte ao dono; confira estado via `showmigrations` e `makemigrations --check --dry-run` (comandos em [AGENTS](../AGENTS.md)); revise operação e impacto sobre dados/lock. Nunca edite migration já aplicada.
3. Rode baseline e valide em banco de desenvolvimento, não `db.sqlite3` existente (`app/settings/dev.py::DATABASES`).

## Testes
- Runner `manage.py test` (Django unittest), classes em `modules/accounts/tests/test_authentication.py::AuthenticationTests`, `modules/organizations/tests/test_privacy.py::PrivacyTests`, `modules/uploads/tests/test_api.py`; fixtures/helpers em `tests/helpers.py::BaseAPITestCase`. Mocks impedem serviços externos quando ajustados. Não há pytest/factory_boy configurados (`pyproject.toml`).
- `ruff check .` e `ruff format --check .` apenas leitura; `[tool.ruff]` em `pyproject.toml`; sem configuração de mypy/pre-commit/CI encontrada no repositório (a confirmar se CI é externa).
- `tests/test_schema.py::OpenApiContractTests` gera o schema sem rede, exige zero warnings/erros, resumo, descrição, tag e `operationId` único por operação. Rode após alterar rotas, serializers ou autenticação; validação estrutural não substitui teste HTTP (`shared/openapi.py::document_viewset`).
