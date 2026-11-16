# Contrato de transição da API — Etapa 3

Este contrato complementa [PLANEJAMENTO.md](PLANEJAMENTO.md). A API anterior não
é um contrato de compatibilidade. Consultar o acompanhamento antes de assumir
que todos os recursos abaixo já estão disponíveis. Frontend em repositório separado.

## Sessão de mesma origem

- `GET /api/csrf/`: público; retorna `csrfToken` e estabelece cookie CSRF.
- `POST /api/login/`: e-mail/senha e `X-CSRFToken`; retorna `detail` e **novo**
  `csrfToken` (rotacionado no login), nunca access/refresh no JSON.
- Access/refresh: cookies host-only, HttpOnly, SameSite=Lax, Path=/; Secure em
  produção. O access alcança `/api/` e `/ws/`. Cookies não devem ser lidos pelo Vue.
- `POST /api/refresh/`: corpo vazio, cookie refresh e CSRF. Rotaciona ambos os
  tokens, invalida o access anterior e atualiza a sessão. Resposta apenas `detail`.
  Duas renovações com o mesmo refresh não são ambas válidas: uma vence; a outra
  recebe 401 sem limpar/sobrescrever os cookies da vencedora. Coordenar via
  single-flight entre requisições/abas e consultar a sessão antes de novo login.
- `POST /api/me/logout/`: CSRF obrigatório, inclusive se a sessão expirou; revoga
  a sessão identificada pelos cookies e limpa ambos com os mesmos atributos.
- `GET /api/users/me/` identifica o usuário após recarga. Bearer **não** autentica
  HTTP nem WebSocket. JWT não é aceito no corpo, URL ou storage do navegador.
- Todas as mutações autenticadas por cookies exigem CSRF. 401 indica ausência,
  expiração ou revogação; 403 não dispara refresh automático (pode ser CSRF ou
  permissão). No máximo uma tentativa de refresh; não repetir mutação de negócio
  automaticamente. Após login em outra aba, renovar o bootstrap CSRF.
- `GET /api/sessions/`, revogação individual e de todas as sessões permanecem.
  A sessão do admin Django permanece separada da sessão da API.
- Produção exige `PUBLIC_ORIGIN=https://host[:porta]` e host em `ALLOWED_HOSTS`.
  CORS é vazio; CSRF e WebSocket têm allowlist explícita da origem pública.
  Desenvolvimento aceita somente as origens locais configuradas, preferindo proxy.

## Decisões de acesso e recursos dependentes

Decisões do dono nesta implementação:

- Ex-vinculados **não** acessam histórico operacional. Registros são preservados;
  prazo de retenção/expurgo continua pendente, sem exclusão automática.
- Avaliação somente por aluno com desembarque registrado em viagem finalizada.
- Relato de objeto por esse aluno ou motorista da viagem. Somente a empresa marca
  encontrado/devolvido, na sequência `reported → found → returned`, sem reabertura
  ou DELETE empresarial.
- Descoberta pública: cidade/UF atendidas e nome do grupo/destino; somente empresas
  aprovadas/ativas, sem endereços/coordenadas operacionais.

## Recursos do domínio datado

Base `/api/`. Listas usam `page`, `page_size` (máximo 100), `total_pages` e
`results`; filtros operam **depois** do isolamento. IDs de domínio são inteiros;
IDs de usuário/sessão e identificadores idempotentes são UUID. Datas/horários de
respostas são relativos a `America/Sao_Paulo`; instantes usam ISO 8601 com fuso.
Schema executável em `/api/schema/`, interface em `/api/doc/`.

| Recurso | Leitura | Escrita explícita |
|---|---|---|
| `memberships/` | Titular e empresa dona; cadastro mínimo do solicitante. | POST `{company_id, profile: passenger|driver}`; `/{id}/approve/`, `reject/`, `withdraw/`, `end/` com `{reason?}`. Sem PATCH/DELETE. |
| `membership-events/` | Mesmo escopo do ciclo. | Somente serviço de vínculo. |
| `group-memberships/` | Titular ativo e empresa dona. | Atribuição via `memberships/{id}/assign-group/` com `{route_group_id, transport_point_id}`; `group-memberships/{id}/authorize-services/` com `{service_ids, habitual_outbound_id}`. |
| `operational-points/` | Somente empresa dona aprovada. | POST/PATCH de endereço operacional completo e coordenadas; empresa/autor inferidos, não aceitos do cliente. |
| `company-route-groups/` | Somente empresa dona aprovada. | POST/PATCH `{name, destination_id}`; `/{id}/policy/`, `generate/`, `cancel-date/`. |
| `response-policies/` | Empresa dona; campos/prorrogação sem defaults universais. | `company-route-groups/{id}/policy/` define abertura, prazo normal e par opcional de prorrogação. |
| `recurring-services/` | Empresa dona. | POST/PATCH de sentido/semana/horário/vigência/duração/margem e IDs escolhidos; `/{id}/stops/` com `{point_ids}`. Grupo não pode ser trocado. |
| `vehicles/` | Empresa dona. | POST/PATCH de placa, capacidade, estado e `garage_point_id`; sem reparenting ou DELETE. |
| `service-days/` | Empresa, aluno elegível ou motorista designado. Sem snapshot agregado contendo pontos de terceiros. | `/{id}/close/` (corpo vazio), `revise/` com `{expected_revision}`, `cancel/` com `{reason}`. Cancelamento informa `partial` e `preserved_travel_ids`. |
| `eligibilities/` | Aluno titular ativo ou empresa. Inclui serviços autorizados e seu próprio ponto/resposta. | `/{id}/answer/`, `request-change/`, `withdraw-leg/` conforme abaixo. |
| `daily-responses/` | Mesmo escopo da elegibilidade. | Sem PATCH genérico; escrita pela elegibilidade. |
| `change-requests/` | Titular ativo/empresa dona. | `/{id}/approve/`, `reject/` com `{reason?}`; `withdraw/`, `apply/` com corpo vazio. Aprovação não transfere imediatamente. |
| `travels/` | Empresa, motorista designado com vínculo ativo ou aluno com participação concreta e vínculo ativo. | Sem POST/PATCH/DELETE genéricos. Ações na tabela seguinte. |
| `travel-participations/` | Empresa/motorista designado: lista da viagem; aluno: somente si. Sem identidade cadastral/endereço pessoal. | `/{id}/record/`, `correct/`; IDs idempotentes obrigatórios. |
| `participation-events/` | Mesmo escopo da participação. | Somente serviços; eventos não editáveis. |
| `route-snapshots/`, `route-stops/` | Somente empresa/motorista designado, nunca por mera associação ao grupo. | Snapshot só por cálculo; `route-stops/{id}/handle/` com `{skipped}`. |
| `travel-publications/` | Mesmo escopo de viagem, incluindo revisões antigas identificáveis. | Somente publicação por serviço. |
| `optimization-jobs/` | Somente empresa dona; estado/erro estático, sem claim, tokens ou entradas congeladas. | Worker, não HTTP. |
| `driver-invitations/` | Empresa e convidado com vínculo ativo. Não concede acesso ao percurso antes da designação. | `/{id}/respond/` com `{accept: true|false}`. |
| `notifications/` | Somente destinatário, inclusive para staff. Payload mínimo não concede acesso ao recurso. | `/{id}/read/` com corpo vazio; idempotente. |
| `driver-ratings/` | Participantes autorizados da viagem; aluno vê apenas sua avaliação. | POST `{travel_id, score: 1..5, comment?}`; repetição igual retorna registro, mudança conflitante é recusada. Sem PATCH/DELETE. |
| `lost-items/` | Empresa/motorista da viagem e autor ainda vinculado; outros alunos não veem relatos. | POST `{travel_id, item_description, operation_id}`; `/{id}/transition/` com `{target_status: found|returned, operation_id}`, somente empresa. Eventos de custódia persistentes e atômicos. |

`passengers/` e `drivers/` agora representam **identidade**, não vínculo: titular
edita apenas seu perfil; empresa ativa lê dados mínimos de vinculados. Não há
DELETE empresarial, `approve/`, `reject/` ou `request-route-group/`. O solicitante
pendente é identificado minimamente no próprio vínculo. `companies/` mantém cadastro
e review separado; `GET companies/?city=&state=&destination=&trade_name=` é público.
`GET companies/me/stats/?date=AAAA-MM-DD` usa dia de atendimento e serviço concretos,
não `started_at` ou todas as viagens agendadas. Staff não recebe bypass operacional;
moderação cadastral continua uma capacidade separada no admin.

### Resposta, pedido e desistência

- `answer/`: `{outbound_service_id: ID|null, return_service_id: ID|null,
  expected_revision: N}`. Inicialmente revisão 0; usar a revisão retornada nas
  edições. Campos nulos com `answered_at` definido são negativa; resposta ausente
  ou `answered_at: null` continuam sem resposta.
- `request-change/`: `{leg: outbound|return, proposed_service_id, expected_revision}`.
  Somente na prorrogação, para serviço autorizado. Decisão e aplicação são distintas;
  ler `status` **e** `application`. Falha conserva escolha/alocação anteriores.
- `withdraw-leg/`: `{leg: outbound|return}`; somente antes do embarque. Invalida
  pedido conflitante sem desfazer outro trecho.

### Ações de viagem e execução

| POST em `travels/{id}/` | Corpo / resultado |
|---|---|
| `calculate/` | `{expected_revision}` → 202 com snapshot pendente; consultar jobs/snapshots. Não executa OSRM no HTTP. |
| `publish/` | `{expected_revision}` → publicação da viagem pronta; não inicia a execução. |
| `start/` | `{expected_revision}`; somente motorista designado, revisão atual publicada. |
| `finish/` | Corpo vazio; somente motorista, sem alunos embarcados ou presenças pendentes. |
| `cancel/` | Corpo vazio; empresa, somente antes de início. |
| `assign-vehicle/` | `{vehicle_id}`; empresa escolhe explicitamente, invalida prontidão. |
| `invite-driver/` | `{driver_membership_id, expires_at}`; empresa escolhe; aceite explícito obrigatório. |
| `unavailability/` | `{operation_id}`; somente motorista designado. |

`GET travels/{id}/location/` retorna `{position: null|{latitude, longitude,
updated_at}, stale}` somente durante operação autorizada. Dados não são embutidos
na listagem de viagens. `publication_current` identifica compatibilidade entre
revisões/ponteiros; publicação antiga não autoriza `start`.

`travel-participations/{id}/record/`: `{kind: boarded|no_show|dropped_off,
operation_id}` pelo motorista. `correct/`: `{corrects_event_id, target_status,
reason, operation_id}` somente pela empresa. Não fabrica desembarque nem reabre
viagem encerrada. Corrigir usa o evento atual, não substitui o histórico.

### Geração, erros e limites de transporte

`company-route-groups/{id}/generate/` recebe `{start_date, horizon_days, batch_size}`,
ambos positivos e no máximo 31 **por requisição HTTP** (limite técnico de carga,
não política/horizonte padrão). `cancel-date/` recebe `{date, reason}` e registra
cancelamento mesmo antes de existir viagem. Nenhuma duração/margem é inventada.

Entradas desconhecidas/protegidas são 400, sem ignorar estados/ownership/revisões.
Erros de domínio têm `{code, detail, errors?}`: 404 para recurso invisível, 403 para
ator sem permissão, 409 para revisão/idempotência/capacidade/transição conflitante,
400 para janela fechada ou dados inválidos. Erros de autenticação/CSRF preservam
`detail` e os status 401/403. Listas vazias não revelam recursos de outras empresas.
API/admin e respostas com cookies usam `private, no-store`, incluindo downloads.

## WebSocket

`/ws/travels/{id}/location/`, mesma origem e cookie de access. Origin obrigatório
na allowlist explícita; tokens em URL/header não autenticam. Cliente reconecta após
refresh; conexão antiga perde o JTI válido. Empresa e aluno autorizado recebem;
somente motorista designado envia:

```json
{"latitude": -26.3, "longitude": -48.8, "recorded_at": "2026-11-16T08:00:00-03:00"}
```

Servidor envia `{type: location, position, stale}`, inclusive posição ausente ou
desatualizada. Sem aceitar binário, campos extras, booleanos como coordenadas,
posição fora de ordem/futura ou payload acima de 1024 bytes. Frequência e idade
usam os limites configurados. Erros não repetem coordenadas. Sessão, conta, vínculo,
alocação e execução são revalidados antes de cada entrega e periodicamente mesmo
sem mensagens. Desistência retira acesso; término limpa posição e fecha o canal.
Códigos: 4001 sessão, 4003 acesso, 4009 operação encerrada/inacessível, 1009 payload,
1000 fechamento normal. GPS não substitui eventos de embarque.

## Admin, worker e clientes de transição

- Formulários genéricos de estado/relacionamentos, add/delete operacionais e ações
  em massa destrutivas são bloqueados. Lista do admin oferece ação explícita de
  domínio para **um** registro, parâmetros JSON validados pelo mesmo contrato e
  `actor_id` do usuário real. Nem superusuário opera por outra empresa implicitamente.
- Worker agora processa snapshots, não Path. Exemplo **apenas fictício** de parâmetros:
  `pdm run worker --once --company-id 1 --lease-seconds 60 --max-attempts 3 --retry-seconds 5`.
  Loop exige também `--poll-seconds`; nenhum número desse exemplo é default universal.
  Agendamento/horizonte persistente e configuração de deploy continuam na Etapa 4.
- `seed_demo_data`/`seed_data` somente dev, `--confirm-fictitious` e `DEMO_PASSWORD`
  no ambiente. Sem reset, senha no log ou dados reais; estrutura idempotente usa
  os serviços novos. Backfill legado de documentos/endereço pessoal foi desativado.
- `paths/`, `route-schedules/`, `confirmations/` e ações de vínculo no perfil foram
  removidos, sem alias que escreva no domínio antigo. Clientes HTML legados não
  representam este contrato e nunca são servidos/coletados como assets.

## SPA e marco integrado

`frontend_dist/index.html` é servido sem interpolação Django, somente GET/HEAD de
navegação com `Accept: text/html`. Deep links sem extensão recebem HTML; o Vue
deve exibir seu próprio 404 para rota desconhecida. Prefixos reservados, arquivos
ausentes, requisições JSON e mutações desconhecidas não recebem fallback HTML.
Somente `/assets/` com extensões aprovadas e `/favicon.ico` são públicos; ocultos,
source maps, manifestos e symlinks são negados. Hashes originais não são renomeados.
HTML usa `no-cache`; assets/favicons revalidam por ETag/Last-Modified, **sem inferir
imutabilidade apenas pelo nome**, até validar o pipeline do build real na Etapa 4.

Este backend foi preparado para artefato, não para servidor Vite em produção.
Fixtures HTML/JS e testes ASGI não comprovam integração com o Vue real: compilação,
rotas efetivas, navegador, cookies de terceiros bloqueados e smoke HTTPS/WSS no
ambiente de entrega permanecem marco conjunto das Etapas 3/4.
