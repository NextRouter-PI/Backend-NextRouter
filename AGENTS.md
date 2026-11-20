# NextRouter — instruções e contexto para agentes no backend

Este documento orienta agentes de IA que trabalham neste repositório.
Todos os caminhos de código e comandos abaixo são relativos à raiz do backend.

## 1. Fontes de verdade e escopo

- **Referências internas do repositório:**
  - [README.md](README.md): instruções de inicialização local (`pdm run dev`), banco de desenvolvimento e execução em rede local (`pdm run dev-lan <IPv4>`).
  - [tests/README.md](tests/README.md): execução opt-in e isolamento da suíte de testes automatizados.
  - [html-template-test/README.md](html-template-test/README.md): painel HTML manual local (servido exclusivamente quando `DEBUG=True`) para inspecionar e exercitar os recursos do contrato datado.
  - [pyproject.toml](pyproject.toml): dependências, scripts PDM e configuração de lint/formatação (Ruff).
  - Código-fonte, testes automatizados e o schema OpenAPI executável (`/api/schema/`, `/api/doc/`) determinam o comportamento implementado.
- **Comportamento e regras de negócio:** o código e a suíte de testes comprovam o
  comportamento atual. Não invente regras de produto silenciosamente diante de
  ambiguidades ou lacunas bloqueantes; confirme com o responsável antes de alterar
  invariantes de domínio ou o contrato HTTP/WS.
- **Superfície entregue pelo backend:** o servidor ASGI entrega na mesma origem a API
  REST (`/api/`), o schema e documentação OpenAPI (`/api/schema/`, `/api/doc/`, `/api/redoc/`),
  o admin (`/admin/`), os canais WebSocket (`/ws/`), os endpoints de saúde (`/health/live/`,
  `/health/ready/`) e, quando `frontend_dist/` estiver presente, os arquivos estáticos
  da interface compilada (`/`, `/assets/`, `/favicon.ico`). Não planeje BFF externo
  nem dependência de cookies de terceiros.
- **Histórico e política de migrations:** nunca crie, altere ou aplique migrations,
  nem use `--fake` ou modifique settings/dependências sem autorização explícita para a
  ação concreta. A base de migrations do repositório parte das quatro `0001_initial`
  atuais para bancos novos/vazios; nunca aplique sobre bancos com schema legado anterior.

## 2. Stack e mapa do repositório

- **Stack:** Python >=3.13, Django >=6.0.7, Django REST Framework >=3.17.1,
  drf-spectacular >=0.30.0, Channels/Daphne (ASGI HTTP+WS), WhiteNoise, PDM e Ruff.
  O processamento assíncrono de rotas utiliza management command (`process_route_jobs`),
  **não Celery**.
- **Perfis de configuração (`app/settings/` e `tests/settings.py`):**
  - `app/settings/base.py`: apps instalados, middlewares, DRF, SimpleJWT, OpenAPI e limites.
  - `app/settings/dev.py`: desenvolvimento local (`pdm run dev` / `dev-lan`); lê `.env`
    se existir, usando por padrão SQLite local (`dev.sqlite3`), cache/canais em memória,
    mídia em `dev-media/`, documentos privados em `dev-private-documents/` e e-mail no console.
  - `app/settings/prod.py`: produção explícita (`PUBLIC_ORIGIN`, HTTPS/WSS, PostgreSQL e Redis obrigatórios).
  - `tests/settings.py`: suíte automatizada (`pdm run test`); ignora `.env`, usa SQLite,
    cache, canais e e-mail em memória e diretórios temporários isolados.
- **Entradas da aplicação (`app/`):**
  - `urls.py` e `api.py`: roteamento HTTP principal, `/api/`, `/api/schema/`, `/api/doc/`, `/admin/`, `/health/` e entrega de `frontend_dist/`.
  - `asgi.py` e `wsgi.py`: entradas ASGI (HTTP + WebSocket com validação de origem) e WSGI.
  - `frontend.py`: `FrontendAssetsMiddleware`, `PrivateResponseMiddleware` (`Cache-Control: private, no-store` em `/api`, `/admin` ou respostas com cookies) e entrega segura de `frontend_dist/`.
  - `runtime_checks.py`, `health.py`, `operational_logging.py` e `html_templates.py` (este último serve `html-template-test/` somente quando `DEBUG=True`).
- **Módulos de domínio (`modules/`) — atenção aos `label`s de app do Django:**
  - `modules/accounts/` (label **`authenticator`**, `AUTH_USER_MODEL = 'authenticator.User'`):
    identidade (`User` UUID), sessões ativas (`UserSession`), códigos por e-mail (`EmailToken`),
    autenticação por cookie + CSRF (`authenticate.py`), autenticação WebSocket (`ws_auth.py`)
    e serviços de conta (`services.py`).
  - `modules/organizations/` (label **`organizations`**): empresas (`Company`), perfis
    de identidade (`Passenger`, `Driver`), ciclo de vínculo (`CompanyMembership`,
    `MembershipEvent`), grupos de atendimento (`CompanyRouteGroup`), vínculo ao grupo
    (`PassengerGroupMembership`), pontos operacionais (`OperationalPoint`), permissões
    (`permissions.py`) e serviços transacionais (`services/memberships.py`, `groups.py`, `participation.py`).
  - `modules/transport/` (label **`router`**): frota (`Vehicle`), configuração habitual
    (`RecurringService`, `ResponsePolicy`), calendário datado (`ServiceDay`,
    `ServiceDayEligibility`, `DailyResponse`, `ChangeRequest`), execução (`Travel`,
    `TravelParticipation`, `ParticipationEvent`, `RouteSnapshot`, `RouteStop`,
    `TravelPublication`), worker/OSRM (`RouteOptimizationJob`, `osrm.py`), convites
    (`DriverInvitation`), pós-viagem (`DriverRating`, `LostItem`, `Notification`),
    agenda automática (`AutomationSchedule`), isolamento de querysets (`access.py`),
    serviços transacionais (`services/`), comandos do admin (`admin_commands.py`) e
    WebSocket de localização (`ws.py`, `routing.py`, `broadcast.py`).
  - `modules/uploads/` (label **`uploader`**): imagens públicas (`Image`) e documentos
    privados (`Document`, sempre gravados em `PRIVATE_DOCUMENT_ROOT` fora de pastas públicas).
- **Utilitários compartilhados (`shared/`):**
  - `domain_api.py`: `DomainViewSet`, `@domain_resource` e `@domain_action` para views finas e schema OpenAPI padronizado.
  - `exceptions.py`: `custom_exception_handler` (mapeia `DjangoValidationError` e erros de integridade para respostas HTTP padronizadas).
  - `frontend_artifact.py`: contrato offline de inspeção, manifesto (`frontend-release.json`), preparo e verificação de `frontend_dist/`.
  - `pagination.py` (`CustomPagination`), `openapi.py`, `address.py`, `geocoding.py`, `admin.py` e `demo.py`.
- **Scripts e testes (`scripts/`, `tests/`, `html-template-test/`):**
  - `scripts/dev.py` (launcher ASGI local/LAN), `scripts/runtime.py` (launcher/preflight de produção), `scripts/frontend_artifact.py` e `scripts/auditar_schema.py`.
  - `tests/helpers.py`: `BaseAPITestCase` e fábricas com dados fictícios válidos.
  - `html-template-test/`: cliente HTML manual para inspecionar o contrato datado em `DEBUG`. Nunca publicar em produção nem incluir em coleta de estáticos.

## 3. Padrões de arquitetura e código

- **Views finas e padronizadas:** views lidam apenas com HTTP, serializers de entrada/saída,
  permissões e querysets previamente isolados. Ao criar ou manter endpoints do domínio
  datado, utilize `DomainViewSet`, `@domain_resource` e `@domain_action` (`shared/domain_api.py`).
- **Services transacionais autoritativos:** toda escrita operacional passa pelos
  serviços de `modules/organizations/services/` e `modules/transport/services/`,
  compartilhados por API, ações explícitas do admin (`admin_commands.py`) e worker.
  O admin não aceita PATCH genérico de estados. Callers legados e espelhamentos por
  signals foram retirados (`organizations.0002_retire_legacy`, `router.0003_retire_legacy`);
  não os reative.
- **Models e garantias de banco:** models concentram regras locais e constraints
  (`UniqueConstraint`, `CheckConstraint`). Não trate `save()` ou signals como garantia
  de integridade (operações em lote podem ignorá-los e `save()` não invoca `full_clean()`
  automaticamente). Revalide invariantes dentro de transações nos services, inclusive
  com bloqueio/concorrência quando aplicável.
- **Contrato de erros (`shared/exceptions.py`):** services levantam
  `django.core.exceptions.ValidationError` com `code` explícito, convertido por
  `custom_exception_handler`:
  - `not_found` → `404 Not Found`
  - `permission_denied` → `403 Forbidden`
  - `stale_revision`, `idempotency_conflict`, `stale_event`, `membership_open`,
    `capacity_exceeded`, `future_allocation`, `operation_in_progress`,
    `invalid_transition` → `409 Conflict`
  - Demais códigos e `InputError` → `400 Bad Request` com `{code, detail, errors?}`.
- **Isolamento de querysets antes de filtros:** filtre todo queryset por empresa,
  vínculo ativo ou participação concreta **antes** de `filterset_fields` ou paginação
  (veja `modules/transport/access.py`). Permissões de objeto (`has_object_permission`)
  não protegem listagens, e `is_staff` **não** concede bypass operacional na API.
- **Convenções gerais:**
  - Novas FKs de usuário devem referenciar `settings.AUTH_USER_MODEL`.
  - URLs e nomes de código em inglês; mensagens de erro e textos voltados ao usuário em português.
  - Fuso horário `America/Sao_Paulo` com `USE_TZ = True`; IDs de domínio inteiros;
    IDs de usuário, sessão e chaves de idempotência (`operation_id`) em UUID.
  - Estilo Ruff ([pyproject.toml](pyproject.toml)): `line-length = 120`, aspas simples (`quote-style = 'single'`).
  - Documente novos endpoints/campos com `drf-spectacular` e cubra negações (`401`, `403`, `404`, `409`).

## 4. Invariantes de domínio e segurança obrigatórias

### Sessão, autenticação e CSRF (`modules/accounts/`)
- **Cookies HttpOnly e mesma origem:** `access_token` e `refresh_token` trafegam apenas
  em cookies host-only, `HttpOnly`, `SameSite=Lax`, `Path=/` (`Secure` em produção),
  alcançando `/api/` e `/ws/`. Cabeçalho `Authorization: Bearer` e JWT em corpo JSON,
  storage ou query string de URL **não** são aceitos.
- **Sessão rastreada:** `CustomAuthentication` valida o JWT do cookie e exige
  `UserSession` ativa correspondente ao `access_jti` e não expirada.
- **Proteção CSRF:** obrigatória em todas as mutações autenticadas por cookie, além de
  `login/`, `refresh/` e `me/logout/`. `GET /api/csrf/` entrega o token de bootstrap
  (CSRF não é JWT). O login rotaciona o token CSRF. Nunca desabilite verificações de
  CSRF, CORS ou Origin HTTP/WS.
- **Códigos por e-mail:** valide sempre o código de confirmação (`EmailToken`) **antes**
  das regras de senha para preservar a contagem de tentativas e a proteção contra enumeração.

### Empresas, perfis, vínculos e grupos (`modules/organizations/`)
- **Identidade separada de vínculo:** `Passenger` e `Driver` representam identidade
  pessoal (editada apenas pelo titular); `Company` tem moderação cadastral própria;
  o vínculo empresarial vive em `CompanyMembership` com histórico em `MembershipEvent`.
- **Unicidade de ciclo empresarial:** cada passageiro ou motorista pode ter no máximo
  **uma empresa ativa** ou **um pedido pendente** por perfil. Só é permitido solicitar
  vínculo a outra empresa após encerrar o vínculo atual ou retirar o pedido pendente.
- **Grupos e bloqueios operacionais:** cada aluno vinculado tem no máximo **um grupo
  ativo** na empresa (`PassengerGroupMembership`), sem limitar retornos autorizados
  nem a atuação de motoristas em múltiplos grupos. Encerrar vínculo, trocar grupo ou
  desaprovar/desativar cadastro exige resolver antes alocações/designações futuras não
  canceladas/desistidas e é bloqueado durante participação operacional em andamento.
- **Histórico restrito:** ex-vinculados perdem acesso ao histórico operacional da
  empresa, mas os registros não são apagados automaticamente.

### Programação habitual, atendimento datado e operação (`modules/transport/`)
- **Decisão humana vs. cálculo de rota:** a empresa escolhe participantes, pontos
  operacionais, motorista e veículo; o OSRM calcula somente a ordem e a trajetória
  das paradas escolhidas. Não implemente alocação automática de alunos, agrupamento
  geográfico autônomo ou escolha heurística de motorista/veículo substituto.
- **Endereço pessoal vs. ponto operacional:** alterar o endereço cadastral do
  passageiro não altera seu ponto operacional de transporte.
- **Configuração habitual (`RecurringService`, `ResponsePolicy`):** duração e margem
  habituais não têm valores padrão universais; sua ausência bloqueia a prontidão.
  Políticas de resposta são configuradas por grupo (janela normal + prorrogação opcional
  com aprovação manual).
- **Geração e regeneração de dias (`ServiceDay`):** a geração automática atinge apenas
  datas futuras não publicadas, preservando respostas, decisões, histórico e dias
  cancelados. Conflitos geram pendência bloqueante até resolução explícita. **Uma única
  viagem publicada congela a regeneração automática de todo o grupo naquela data**;
  alterações posteriores exigem revisão explícita (`revise/` com `expected_revision`).
- **Respostas diárias e mudanças na prorrogação (`DailyResponse`, `ChangeRequest`):**
  ida e retorno são independentes. Ausência de resposta (`answered_at IS NULL`) é
  distinta de negativa explícita. Pedidos na prorrogação exigem aprovação antes do fim
  da janela, mas **a aprovação não transfere o aluno imediatamente**: a escolha e a
  alocação anteriores são preservadas até que o cálculo seja validado e a mudança
  seja aplicada atomicamente (`apply/`). Desistência por trecho (`withdraw-leg/`) é
  permitida antes do embarque e invalida pedido conflitante.
- **Cálculo, publicação e execução (`Travel`, `TravelParticipation`):** aceitar pedido,
  calcular rota e publicar viagem são operações distintas; uma viagem por serviço/data.
  Cancelamento de dia preserva viagens já iniciadas ou finalizadas e informa parcialidade.
  Motorista substituto exige convite e aceite explícito (`DriverInvitation`).
  Somente a empresa pode corrigir presença (`correct/`), com motivo, referência e
  auditoria, sem fabricar desembarque nem reabrir viagem encerrada.
- **Pós-viagem e comunicação:** avaliação (`DriverRating`) só pode ser registrada por
  aluno com desembarque confirmado em viagem finalizada. Objetos perdidos (`LostItem`)
  seguem estritamente `reported → found → returned` (transições feitas apenas pela
  empresa, com `operation_id` e auditoria, sem reabertura ou DELETE). Avisos
  (`Notification`) são restritos ao destinatário (inclusive para staff).
- **Worker e automação:** `process_route_jobs` exige escopo explícito (`--company-id` ou `--all-companies`, e em produção `WORKER_COMPANY_ID` ou `WORKER_ALL_COMPANIES=true`), além de lease, tentativas, retry,
  poll e lotes explícitos. A agenda automática opt-in por grupo (`router.0004_automation_schedule`)
  persiste horizonte, lote, frequência e checkpoint transacional no banco.

### Privacidade, documentos e entrega estática (`modules/uploads/`, `app/frontend.py`)
- **Proteção de dados pessoais:** passageiros podem ser menores de idade. Nunca exponha
  identidade cadastral, endereço pessoal ou localização a outros passageiros e **nunca
  registre em logs** senha, código de verificação, JWT, CPF, endereço ou coordenadas.
- **Armazenamento separado:** imagens usam `MEDIA_ROOT` (`/media/` ou Cloudinary);
  documentos privados (`Document`) usam sempre `PRIVATE_DOCUMENT_ROOT` (caminho absoluto
  fora de `MEDIA_ROOT`, `STATIC_ROOT`, `FRONTEND_DIST` e `STATICFILES_DIRS`) e só são
  entregues após verificação de permissão na API.
- **Artefato estático (`frontend_dist/`):** inspecionado por `shared/frontend_artifact.py`,
  aceita apenas `index.html`, `favicon.ico` e arquivos com extensão permitida sob
  `assets/`, sem symlinks, arquivos ocultos, service workers ou manifestos públicos fora
  da allowlist. Rotas reservadas (`api`, `admin`, `ws`, `assets`, `static`, `media`,
  `uploads`, `downloads`, `private-documents`, `html-template-test`, `frontend_dist`,
  `health`) e caminhos com ponto nunca recebem fallback HTML.

## 5. Ambiente, segurança de execução e validação

- **Autorização prévia obrigatória:** não crie nem execute testes, builds, servidores
  ou migrations automaticamente por padrão. Peça autorização explícita antes de criar
  ou aplicar migrations, alterar settings/dependências, iniciar servidores/workers,
  acessar bancos de dados ou executar operações destrutivas. Nunca toque no banco
  habitual nem em serviços externos reais.
- **Comandos de desenvolvimento (somente quando autorizados):**
  - `pdm run dev`: inicia apenas Django/Daphne em `127.0.0.1:8000` com `app.settings.dev`
    (não instala pacotes, não aplica migrations e não cria dados).
  - `pdm run dev-lan <IPv4>`: abre bind na rede local confiável autorizando explicitamente
    o IPv4 informado em `ALLOWED_HOSTS` e nas origens CSRF/CORS/WS.
  - Atenção ao `.env`: `app.settings.dev` carrega automaticamente `.env` quando presente,
    e valores preenchidos prevalecem sobre o terminal (podendo apontar para PostgreSQL,
    Redis, SMTP, Cloudinary, OSRM ou Geocoding reais). Confira sempre o ambiente antes
    de iniciar qualquer processo.
- **Isolamento para verificações estáticas e de schema (`lint`, `check`, `schema`):**
  como `pdm run check` (que inclui `makemigrations --check --dry-run`) e `pdm run schema`
  usam `app.settings.dev`, bloqueie a leitura do `.env` habitual com `NEXTROUTER_ENV_FILE`
  apontando para um caminho inexistente e isole os caminhos/serviços:

```sh
export NEXTROUTER_ENV_FILE=/tmp/opencode/nextrouter-env-inexistente
export DATABASE_URL=sqlite:////tmp/opencode/nextrouter-autorizado.sqlite3
export MEDIA_ROOT=/tmp/opencode/nextrouter-autorizado-media
export PRIVATE_DOCUMENT_ROOT=/tmp/opencode/nextrouter-autorizado-private
export REDIS_URL=
export GEOCODING_URL=
export OSRM_URL=
export EMAIL_HOST=
export CLOUDINARY_URL=
pdm run lint
pdm run check
pdm run schema
```

- **Execução de testes ([tests/README.md](tests/README.md), somente quando autorizada):**
  - `pdm run test` e `pdm run test <modulo.classe.metodo>`: usam `tests.settings`
    (sem ler `.env`, com SQLite em memória e diretórios temporários em `/tmp`),
    excluindo a tag `migration`. O runner do Django cria e migra o banco de teste em memória.
  - `pdm run test-migrations`: executa a regressão de guardas de retirada do schema legado (`--tag=migration`).
  - `pdm run test-html`: executa os testes Node (`tests/html_client.test.mjs`) do cliente HTML local.
  - **Limites de evidência:** SQLite e canais em memória não comprovam locks/concorrência
    de PostgreSQL nem comunicação Redis entre processos.
- **Mudanças exclusivamente documentais:** verifique links, consistência com o código
  e `git diff --check`; não execute testes funcionais sem necessidade ou autorização,
  e nunca apresente validações históricas como se tivessem sido executadas na revisão atual.

## 6. Commits e documentação

- **Commits atômicos por mudança lógica:** siga o padrão do histórico (`git log`),
  usando prefixos `feat:`, `fix:`, `chore:`, `docs:` ou `test:` com descrição curta em
  português.
- **Escopo limpo:** inclua implementação, testes e documentação do repositório que
  pertençam à mesma mudança lógica no mesmo commit. Confirme `git status` e
  `git diff --check` antes de versionar. Não misture assuntos independentes, trabalho
  preexistente ou artefatos temporários (`dev.sqlite3`, `dev-media/`, `frontend_dist/`
  de trabalho), e nunca faça `git push` ou `git merge` sem pedido explícito.
- **Manutenção documental:** ao alterar comportamento, scripts, configurações ou
  endpoints, mantenha atualizados o schema OpenAPI e a documentação interna afetada
  ([README.md](README.md), [tests/README.md](tests/README.md),
  [html-template-test/README.md](html-template-test/README.md) e este [AGENTS.md](AGENTS.md)),
  registrando com precisão o que foi ou não validado.
