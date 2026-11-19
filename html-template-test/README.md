# Site HTML de testes locais

Cliente do contrato datado atual, em **HTML sem estilização** e com JavaScript
funcional, sem CSS, frameworks, npm ou build. Inclui fluxos navegáveis por perfil
e [painel técnico](painel.html) com todas as operações do OpenAPI executável.
As chamadas são reais: não há login fictício, sucesso simulado ou alocação automática.
**Mapa adiado**; a seleção de alunos usa listas/checkboxes.

Fontes de verdade na raiz do workspace: [CONTRATO_API.md](../../CONTRATO_API.md),
[PLANEJAMENTO.md](../../PLANEJAMENTO.md) (seção 15) e o OpenAPI em `/api/schema/`.
Inventário por fluxo em [COBERTURA.md](COBERTURA.md).

## 1. Como abrir

Use o Django/Daphne, **na mesma origem** da API e do WebSocket:

```text
http://127.0.0.1:8000/html-template-test/
```

Não abra por `file://`, `python -m http.server`, porta 5173 ou uma URL de API
configurada no navegador. Não é necessário relaxar CORS, CSRF ou Origin WS.
A raiz `/` e o contrato do artefato Vue não foram alterados.

### Ambiente local já preparado

Execute os comandos deste guia em `backend/`.

Antes de iniciar, confirme um banco descartável com as migrations atuais aplicadas.
O SQLite habitual do repositório pode estar incompatível; **não o use nem migre
seguindo automaticamente este tutorial**. O perfil dev não lê `.env`; informe
os caminhos próprios no terminal do servidor:

```sh
# Diretório absoluto descartável previamente preparado/autorizado.
: "${HTML_TEST_ROOT:?Informe o diretório descartável autorizado}"
export DEV_DATABASE_PATH="$HTML_TEST_ROOT/db.sqlite3"
export DEV_MEDIA_ROOT="$HTML_TEST_ROOT/media"
export DEV_PRIVATE_DOCUMENT_ROOT="$HTML_TEST_ROOT/private-documents"
export DEV_FRONTEND_ORIGIN=http://127.0.0.1:8000
export DEV_GEOCODING_URL=
export DEV_OSRM_URL=
pdm run dev
```

Prefira `127.0.0.1` em todos os links, sem alternar para `localhost` durante a sessão.
Sem Redis, os canais funcionam somente em **um** processo ASGI. Isso não comprova
operação multiprocesso ou produção. O servidor não aplica migrations nem cria dados.

### Preparação manual opcional — somente banco novo e fictício autorizado

Se ainda não houver banco preparado, os comandos abaixo criam **outro** diretório
e aplicam as migrations existentes nele. Obtenha autorização concreta antes de
executá-los; não substitua o caminho pelo banco habitual, não use `--fake` e não
reaproveite um banco legado:

```sh
HTML_TEST_ROOT=$(mktemp -d /tmp/opencode/nextrouter-html-XXXXXX)
export DEV_DATABASE_PATH="$HTML_TEST_ROOT/db.sqlite3"
export DEV_MEDIA_ROOT="$HTML_TEST_ROOT/media"
export DEV_PRIVATE_DOCUMENT_ROOT="$HTML_TEST_ROOT/private-documents"
export DEV_FRONTEND_ORIGIN=http://127.0.0.1:8000
export DEV_GEOCODING_URL=
export DEV_OSRM_URL=
pdm run migrate
# Digite uma senha fictícia em tempo de uso, sem gravá-la no histórico/arquivos.
read -r -s -p 'Senha fictícia da demonstração: ' DEMO_PASSWORD
export DEMO_PASSWORD
pdm run python manage.py seed_demo_data --settings=app.settings.dev --confirm-fictitious
unset DEMO_PASSWORD
pdm run dev
```

A fixture existente usa `company@fixture.example.invalid`,
`driver@fixture.example.invalid`, `passenger@fixture.example.invalid` e
`moderator@fixture.example.invalid`. A senha é a informada no ambiente; não é
exibida, redefinida em reexecuções ou incluída nos HTMLs. Os códigos de cadastro/
recuperação usam o e-mail de autenticação (console local com SMTP desabilitado).

Não se cria worker, provedor de trajeto ou publicação automaticamente. Com OSRM
desabilitado, um cálculo não fica pronto por abrir esta página. Configure um serviço
autorizado e execute o worker separadamente com todos os limites explícitos do
[contrato](../../CONTRATO_API.md). Nunca envie coordenadas reais a um provedor por
seguir este roteiro. Remova recursos descartáveis somente depois de encerrar seus
processos e conferir exatamente os caminhos próprios.

## 2. Sessão e segurança

- Login usa bootstrap CSRF e cookies HttpOnly. Access/refresh não são lidos, exibidos
  ou persistidos pelo JavaScript; não há Bearer, JWT em URL ou storage.
- O perfil é consultado pelos endpoints `me/`; `/api/users/me/` não possui um campo
  de papel. Moderação no Admin tem sessão separada e não concede bypass operacional.
- Recarregar a página consulta a sessão real. Abas compartilham cookies; use perfis
  de navegador separados para operar como empresa, motorista e aluno simultaneamente.
- GET autenticado pode tentar uma renovação e repetir **somente essa leitura**.
  Refresh é single-flight na página e coordenado por Web Locks entre abas; sem essa
  API, use renovação manual em uma única aba. BroadcastChannel transmite apenas eventos,
  nunca credenciais. Login/logout em outra aba invalidam a interface; foco relê a conta.
- Mutações nunca são repetidas automaticamente. 403 não dispara refresh; 409 exige
  releitura e nova decisão. Um UUID idempotente precisa ser mantido ao verificar uma
  falha de rede. Novo UUID significa nova operação.
- Campos opcionais oferecem **não enviar**, **enviar valor** e, quando permitido,
  **enviar nulo**. Política, duração/margem e limites de agenda não têm defaults
  inventados. Instantes são ISO 8601 com fuso explícito.
- Resultados autorizados ficam no DOM da página, sem persistência ou console de
  payloads. Diagnósticos mascaram valores livres, códigos, CPF, endereço e coordenadas.
  Use somente dados fictícios; não exporte capturas com dados reais.

## 3. Fluxo sugerido

1. **Conta/empresa:** solicite/verifique código, envie documentos e confirme cadastro.
   Modere a empresa pelo Admin, sem alterar estado operacional em formulários genéricos.
2. **Configuração:** pontos → grupo/destino → frota/motorista → política → serviços
   com dias, vigência, duração e margem escolhidos pela empresa.
3. **Vínculos:** titular solicita; empresa aprova, atribui grupo/ponto e autoriza serviços.
4. **Seleção habitual:** em Programação habitual, carregue grupo, serviço e alunos.
   Na ida, marcar escolhe a ida habitual e mantém outras autorizações; desmarcar
   somente retira o caráter habitual. No retorno, altera apenas aquela autorização.
   Para retirar outra autorização, use a ação individual `authorize-services/`.
   Salvamento é **individual**, não transação coletiva. Confira resultados parciais.
   Há releitura prévia, mas a API não oferece revisão otimista dessa configuração;
   não há promessa de proteção completa contra edições concorrentes.
5. **Atendimento:** gere horizonte/dias explicitamente ou configure agenda opt-in.
   O aluno responde na janela normal; ausência de resposta é diferente de negativa.
6. **Planejamento:** após prazo, feche o dia, acompanhe jobs/snapshots, resolva
   pendências e publique cada viagem. Aprovar pedido não transfere antes de cálculo
   válido/aplicação. Convite de substituto exige aceite explícito.
7. **Execução:** motorista designado inicia a publicação atual, registra presença,
   avança paradas e finaliza sem pendências. Correção é empresarial e auditada.
8. **Localização:** selecione viagem ativa e conecte. Motorista envia ponto avulso
   explicitamente; GPS apenas preenche os campos com permissão, sem envio automático.
   Ausência/stale/fechamento são visíveis. Renovação reconecta o socket, não reenvia GPS.
9. **Pós-viagem:** aluno desembarcado avalia/relata objeto; empresa conduz
   `reported → found → returned`. Avisos são consultados e marcados como lidos.

Nas listas, use **Carregar / atualizar registros**, filtros, paginação e
**Abrir e escolher ação**. As ações usam a revisão lida do servidor; não há PATCH
genérico de estados. Depois de uma mutação bem-sucedida, reabra a ação para obter
estado/revisão atualizados antes da próxima operação.

## 4. Validação

Os testes Python verificam entrega/allowlist, negações em produção, HEAD/métodos,
traversal/symlinks, navegação sem CSS, contrato e campos de leitura. A suíte executa
também os testes nativos JS quando Node >=22 está disponível:

```sh
node --test tests/html_client.test.mjs
```

Smoke opcional com **Node >=22 e Firefox já instalados**, sem npm, Playwright ou
driver. O comando exige confirmação fictícia, cria banco/arquivos/perfis em diretório
novo sob `/tmp/opencode`, ignora URLs herdadas de serviços, migra/semeia apenas o
próprio banco e encerra/remove somente os próprios recursos:

```sh
node scripts/test_html_browser.mjs --confirm-fictitious
```

O smoke usa OSRM fictício apenas na preparação de uma viagem pelo domínio, sem
chamar a rede. Testa páginas/formulários, sessão, seleção, início e WS pelo navegador
local. Não comprova o Vue real, HTTPS/WSS, concorrência PostgreSQL, Redis multiprocesso,
provedor, GPS real/celular suspenso ou todas as regras de negócio em cada formulário.
Consulte a evidência executada e os limites atuais no planejamento; existência do
roteiro ou de cobertura no catálogo não significa execução aprovada.

## 5. Isolamento da produção

O servidor local tem allowlist de HTML/JS/catálogo, aceita GET/HEAD e exige DEBUG.
README, cobertura, diretórios, ocultos, symlinks e arquivos não listados não são
publicados. Há `private, no-store`, CSP sem estilos/scripts inline e links sem
referer para outras origens. `Referrer-Policy: same-origin` preserva o Origin dos
POSTs locais necessário ao CSRF. Nenhuma pasta inteira do repositório vira raiz pública.

`html-template-test/` continua fora de STATICFILES_DIRS, collectstatic e do
artefato Vue. Em produção, as URLs retornam 404 mesmo se os arquivos existirem.

**Ajuste de ambiente de 2026-11-18:** exemplos atualizados para o novo perfil dev;
nenhum desses comandos, testes ou migrations foi executado neste recorte. O
cliente HTML não comprova a integração do Vue.
