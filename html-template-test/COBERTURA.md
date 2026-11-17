# Cobertura do cliente HTML — contrato datado

[README](README.md) · [Contrato](../CONTRATO_API.md) ·
[Planejamento](../PLANEJAMENTO.md), seção 15.

## Catálogo executável

`painel.html` carrega `GET /api/schema/` em JSON e enumera **cada combinação
método/caminho** descrita no OpenAPI atual: GET, POST, PATCH, PUT e DELETE quando
existirem. Formulários usam o schema de path/query/body, inclusive UUID, valores
nulos, omissão, cadastro polimórfico e multipart. Não há cópia versionada do schema
nem aliases operacionais para os recursos retirados.

Esse catálogo inclui as operações administrativas de `users/`, aliases `token/`
e `email-tokens/`, perfis/empresas e seus endpoints `me/`, uploads e downloads.
Permissões continuam sendo as da API; estar no seletor não autoriza executar.
HEAD/OPTIONS implícitos não possuem formulário separado; HEAD da entrega é testado
automaticamente. Swagger/Redoc/Admin e probes têm links nativos na página inicial.

**Cobertura de formulário não equivale a execução ponta a ponta de cada operação.**
Os recursos abaixo também têm listas/ações e navegação de domínio fora do painel.

## Mapa por fluxo

Base dos caminhos: `/api/`. Ações são **POST**, salvo leitura indicada. Escritas
genéricas só aparecem onde o código atual realmente oferece POST/PATCH/PUT/DELETE.

| Página | Recursos / ações |
|---|---|
| `index.html` | CSRF, login, refresh, logout e consulta de conta/perfis; descoberta pública `companies/` com filtros e paginação; links de documentação/Admin/probes. |
| `contas.html` | `registration/request`, `verify`, `confirm`; `password-reset/request`, `verify`, `confirm`; `email-change/request`, `verify`, `confirm`; `users/me/`; `sessions/`, revogação individual, `me/revoke-sessions/`, `me/deactivate/`. |
| `empresas.html` | `companies/me/`, `companies/me/stats/?date=`; uploads de imagens/PDFs e download privado por UUID. Cadastro de empresa pelo fluxo polimórfico em Contas. |
| `vinculos.html` | `memberships/`: solicitar, `approve`, `reject`, `withdraw`, `end`, `assign-group`; `group-memberships/` e `authorize-services`; `membership-events/`; identidade `passengers/` e `passengers/me/`. |
| `grupos-horarios.html` | `operational-points/`, `company-route-groups/`, `response-policies/`, `recurring-services/`; ações `policy`, `generate`, `cancel-date`, `automation`, GET `automation-status`, `stops`; seleção manual de alunos/autorizações por checkbox. |
| `veiculos-motoristas.html` | `vehicles/`, `drivers/` e `drivers/me/`; identidade e vínculo separados, sem DELETE empresarial de perfil/frota. |
| `agenda-respostas.html` | `service-days/`: `close`, `revise`, `cancel`; `eligibilities/`: `answer`, `request-change`, `withdraw-leg`; `daily-responses/`; `change-requests/`: `approve`, `reject`, `withdraw`, `apply`. |
| `trajeto-osrm.html` | `travels/`: `calculate`, `publish`, `assign-vehicle`, `invite-driver`, cancelamento conforme papel; `optimization-jobs/`, `route-snapshots/`, `route-stops/`, `travel-publications/`. |
| `viagens-presenca.html` | `travels/`: `start`, `finish`, `unavailability`; `driver-invitations/respond`; `travel-participations/record`, `correct`; `participation-events/`; `route-stops/handle`. |
| `ws-localizacao.html` | GET `travels/{id}/location/`; WS `/ws/travels/{id}/location/`, cookie + Origin, ponto avulso explícito/GPS apenas preenchimento, ausência/stale, refresh/reconexão e códigos de fechamento. |
| `objetos-avaliacoes.html` | `driver-ratings/`; `lost-items/` e `transition`, com custódia auditada/forward-only e UUIDs. |
| `avisos.html` | `notifications/`, detalhe e `read` idempotente. |
| `painel.html` | Todas as operações HTTP do schema carregado, inclusive detalhes, filtros, identidades administrativas e aliases atuais não repetidos no fluxo principal. |

Os arquivos `grupos-horarios.html`, `trajeto-osrm.html` e `viagens-presenca.html`
mantêm seus nomes locais, mas **não** representam os contratos antigos de horários
pareados/Path/confirmação. `paths/`, `route-schedules/`, `confirmations/`, Bearer e
ações de vínculo no perfil não são usados.

## Dados de leitura necessários

- `group-memberships/`: `service_ids` + `habitual_outbound_id` real ou `null`.
- `recurring-services/`: `point_ids` das paradas configuradas, na ordem salva.
- `eligibilities/`: serviços autorizados mínimos e resposta/revisão do próprio aluno.
- A revisão e os UUIDs são tratados explicitamente; o cliente não escolhe participantes,
  motoristas, veículos, políticas ou duração/margem por heurística/default universal.
- Falha de cálculo não é sucesso, agenda não inicia worker, aceite não aplica pedido,
  publicação não inicia viagem, GPS não é presença e edição em lote de autorizações
  não é uma transação coletiva. O mapa permanece adiado.

## Verificações automatizadas

`tests/test_html_templates.py` confere que os recursos/operações declarados em
`assets/workflows.json` existem no OpenAPI, valida links/arquivos e impede estilos,
storage de sessão no cliente e publicação em produção. O painel deriva sua lista do
schema em execução, inclusive operações futuras. `tests/html_client.test.mjs` cobre
CSRF/refresh/negações, ausência de replay, URLs e diagnóstico, preservação de
autorizações, referências do schema e derivação WS/WSS.

`scripts/test_html_browser.mjs` é smoke opcional em Firefox sobre banco novo e
fixture; não roda automaticamente na suíte Python nem instala ferramentas. A evidência
de execução, seus limites e o estado do marco Vue real permanecem no planejamento.
