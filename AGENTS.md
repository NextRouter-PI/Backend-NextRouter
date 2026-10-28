# NextRouter — contexto para agentes

## Visão
Backend Django de transporte de passageiros por empresas: grupos de rota, motoristas, veículos, viagens e localização ao vivo (`modules/transport/models/travel.py::Travel`).
O passageiro é o próprio aluno, possivelmente menor de idade; empresa, motorista, passageiro e administrador da plataforma são os papéis (`modules/organizations/models/passenger.py::Passenger`, `modules/accounts/models/user.py::User`).
Frontend em outro repositório (decisão do dono; URLs de integração em `app/settings/base.py::FRONTEND_URL`).

## Stack
- Python >=3.13, Django >=6.0.7; DRF >=3.17.1 e drf-spectacular >=0.30.0 (`pyproject.toml`, `app/settings/base.py::REST_FRAMEWORK`).
- PDM (`pdm.lock`), Ruff (lint/formatação), Django TestCase; Channels/Daphne ASGI; worker por management command, **não Celery** (`pyproject.toml`, `app/asgi.py::application`, `modules/transport/management/commands/process_route_jobs.py::Command`).
- SQLite opcional em dev, PostgreSQL e Redis obrigatórios em prod (`app/settings/dev.py::DATABASES`, `app/settings/prod.py::DATABASES`, `app/settings/base.py::CHANNEL_LAYERS`).

## Comandos (na raiz, PDM; use banco temporário ao testar)
```sh
pdm sync --dry-run --no-self -q    # dry-run passou; instalação real não verificada: exige acesso ao índice
pdm run dev --help                # help verificado; alias do runserver
pdm run runserver --help          # servidor local iniciado e encerrado por timeout
pdm run asgi --help               # ASGI local iniciado e encerrado por timeout; usa app.settings.dev
pdm run worker --help             # help verificado; worker DB de rotas, não Celery
pdm run migrate --help            # help verificado; migrate real altera banco, peça antes
pdm run check                     # check e makemigrations --check --dry-run: passaram
pdm run test                      # 46 testes passaram; arquivo: pdm run test modules.accounts.tests.test_authentication (13 passaram)
pdm run lint                      # ruff check . e ruff format --check .: passaram
pdm run format                    # format e lint --fix: passou
pdm run schema                    # spectacular --validate --fail-on-warn: passou
pdm run check-deploy              # passou, 0 avisos, com variáveis fictícias inline; sem env falha imediatamente
```
`manage.py` usa `app.settings.dev`; ASGI/WSGI usam `app.settings.prod` por padrão. Antes de testar, force `DATABASE_URL=sqlite:////tmp/opencode/nextrouter-dev.sqlite3 REDIS_URL= GEOCODING_URL= OSRM_URL= EMAIL_HOST=`; o dev lê `.env` e variáveis do shell prevalecem (`app/settings/dev.py::DATABASES`, `app/settings/dev.py::EMAIL_BACKEND`). Para `check-deploy`, forneça os nomes obrigatórios de [ARQUITETURA](docs/ARQUITETURA.md); nunca grave valores reais nos docs. Não inicie worker com dados reais sem pedido.

## Mapa
- `app/settings/`: `base.py` comum, `dev.py` local, `prod.py` estrito; `app/`: rotas, ASGI/admin (`app/api.py::router`, `app/asgi.py::application`).
- `modules/accounts/`: usuário UUID, JWT/sessões e códigos por e-mail (`modules/accounts/models/user.py::User`).
- `modules/organizations/`: empresas, grupos, vínculos e aprovação (`modules/organizations/models/company_route_group.py::CompanyRouteGroup`).
- `modules/transport/`: horários, veículos, viagens, presença, trajeto OSRM e WS (`modules/transport/models/travel.py::Travel`).
- `modules/uploads/`: upload e download restrito de documentos (`modules/uploads/api/views.py::DocumentUploadViewSet`).
- `shared/`: paginação, erros, endereços e geocodificação (`shared/pagination.py::CustomPagination`).
- `tests/`: helpers de API; `docs/` e `html-template-test/`: contexto e clientes manuais (`tests/helpers.py::BaseAPITestCase`).

## Invariantes e limites
- Não proponha rota nem escolha motorista automaticamente: pessoas escolhem endereços e motorista; OSRM só calcula a ordem/trajetória das paradas escolhidas (`modules/transport/api/serializers/travel.py::TravelCreateSerializer`, `modules/transport/optimization.py::process_optimization`).
- Só motorista designado e aprovado inicia/finaliza viagem; empresa aprovada cria/cancela; preserve estados e presença (`modules/transport/api/views/travel.py::TravelViewSet`).
- Valide código de confirmação **antes** das regras de senha: decisão do dono, **ainda não cumprida em todos os fluxos**; veja [divergências](docs/PROGRESSO.md) (`modules/accounts/api/serializers/email_token.py::PasswordResetSerializer`).
- Isole dados por empresa e trate identidade, endereço e localização de alunos como LGPD: não exponha em respostas, logs ou testes reais (`modules/organizations/api/views/passenger.py::PassengerViewSet`, `modules/transport/consumers.py::TravelLocationConsumer`). Não registre senhas, códigos, JWT, CPF, endereços ou coordenadas (`modules/accounts/services.py::send_email_token`).
- API consumida por outro repositório: mudanças de contrato só aditivas ou versionadas e documentadas (`app/api.py::router`; decisão do dono).
- Pergunte antes de migrations, settings, dependências, mudança de contrato ou operação destrutiva; nunca edite migration aplicada, apague dados, exponha segredos, faça push/merge sem pedido (`modules/transport/models/travel.py::Travel`, `app/settings/prod.py::DATABASES`).
- Leia [progresso](docs/PROGRESSO.md), rode baseline, faça alterações pequenas, commit por mudança lógica. Atualize documentos de comportamento/comandos/decisões **no mesmo commit** da mudança (`docs/PROGRESSO.md`).

## Leitura sob demanda
- Antes de mexer em papéis, estados, viagens ou trajetos: [DOMINIO](docs/DOMINIO.md).
- Antes de mexer em autenticação, tempo real, integrações ou settings: [ARQUITETURA](docs/ARQUITETURA.md).
- Antes de criar endpoint/model/teste: [CONVENCOES](docs/CONVENCOES.md).
- Antes de contrariar uma escolha de produto: [DECISOES](docs/DECISOES.md).
- Antes de começar/terminar sessão: [PROGRESSO](docs/PROGRESSO.md).
