# Ambiente e operação — Etapa 4

Referência local, sem provedor escolhido ou deploy autorizado. Complementa
[PLANEJAMENTO.md](PLANEJAMENTO.md), [BUILD_VUE.md](BUILD_VUE.md) e
[CONTRATO_API.md](CONTRATO_API.md). Build Vue real e navegador continuam pendentes;
fixtures não são uma entrega do frontend. Não executar este código sobre o banco
habitual sem os incrementos e uma estratégia concretamente autorizada.

## 1. Entrega identificada

- Python 3.13, PDM fixado com seu extra oficial `locked` no build, dependências Python
  do `pdm.lock` com verificação de atualização
  (`pdm install --check --prod --no-self --no-editable`). Nenhuma
  resolução/atualização de dependências faz parte do startup.
- A imagem `release` exige `frontend_dist/` e `frontend-release.json` preparados
  conforme BUILD_VUE.md. A revisão completa do backend deve coincidir com o manifesto.
  Sem frontend, o build de release falha; o target `backend` serve apenas para
  trabalhos isolados, não para declarar entrega conjunta.
- Node, PDM, repositório Git, `.env`, testes, dados locais e cliente HTML legado não
  fazem parte do runtime. Coleta de `/static/` ocorre offline no build, usando
  `app.settings.build`, sem PostgreSQL/Redis/SMTP ou segredos. **Nunca** iniciar web
  ou worker com esses settings de build.
- Na CI futura, fazer checkout limpo de revisões completas dos dois repositórios,
  respeitar Node/lockfile do Vue, compilar, preparar o manifesto e construir uma
  imagem única. O preparador não compila nem autentica a origem de um artefato:
  SHA-256 detecta alteração, não substitui checkout confiável/assinatura.
- Registrar commits e digest da imagem no release. Os defaults das imagens de
  infraestrutura são referências de desenvolvimento; fixar `PYTHON_IMAGE`,
  `NGINX_IMAGE`, `POSTGRES_IMAGE` e `REDIS_IMAGE` por digest no release e revisar
  atualizações de segurança. Pacotes do sistema vêm do repositório Debian, sem
  snapshot apt: não há promessa de reprodução byte a byte de builds futuros.

## 2. Configuração e borda TLS

Usar `.env.example` como inventário, nunca preencher esse arquivo versionado com
valores reais. Produção lê o ambiente; Compose deve receber `--env-file` explícito,
em arquivo privado fora do Git. Não imprimir `docker compose config` com valores
reais; `config --quiet` valida sem exibir credenciais. Não passar segredos como
build args, URLs públicas ou variáveis `VITE_*`.

`compose.yaml` é referência de uma borda NGINX controlada:

- Apenas TLS do proxy é publicado, em `127.0.0.1:${HTTPS_PORT}`. PostgreSQL/Redis e
  Daphne não têm portas publicadas. Rede `backend` é interna; web/worker também
  alcançam `edge` para SMTP/serviços autorizados. Proxy acessa web pela rede edge.
- `deploy/nginx.conf` encaminha todas as URLs ao backend, sem montar mídia/arquivos
  privados como raiz pública. Suporta upgrade WebSocket, sobrescreve Proto/For/IP
  e remove Forwarded/Forwarded-Host/Port/Daphne-Root-Path recebidos do cliente.
- Certificado `cert.pem` e chave `key.pem` vêm de `TLS_DIRECTORY`, fora do Git e da
  imagem. Certificado autoassinado do smoke é exclusivamente local. Em provedor,
  validar emissão/renovação, DNS, redirecionamento HTTP e topologia real antes do uso.
- `TRUST_PROXY_HEADERS=false` por padrão em produção. Compose o habilita porque
  define essa borda e não expõe Daphne diretamente. Só habilitar em outra topologia
  após comprovar que a borda descarta headers forjados e que o acesso direto ao
  backend é bloqueado. Não habilitar `--proxy-headers` do Daphne por conveniência.
- Origin HTTPS único em `PUBLIC_ORIGIN`, host em `ALLOWED_HOSTS`; CORS vazio, cookies
  Secure/HttpOnly/Lax e CSRF/Origin WS continuam obrigatórios. Links de frontend em
  produção usam essa origem, não os hosts legados de desenvolvimento.
- DRF ignora IP encaminhado sem confiança explícita; nessa referência confia em
  um único valor X-Forwarded-For sobrescrito pela borda. O IP da sessão é o peer
  direto, não um X-Forwarded-For arbitrário. Rever limites de abuso na topologia real.
- HSTS começa em 0; configurar `HSTS_SECONDS` deliberadamente após testar HTTPS.
  Include-subdomains/preload ficam desligados, inclusive no Compose, sem assumir
  controle do domínio do provedor. `check --deploy` pode emitir W004, W005 ou W021
  conforme a fase; registrar a justificativa, não silenciar ou ativar preload para
  esconder avisos. `release-check` reprova erros, não essas decisões pendentes.

PostgreSQL/Redis remotos precisam de rede privada/autenticação/TLS conforme o
provedor. A rede interna local não comprova segurança de um serviço público.
`OSRM_URL`/`GEOCODING_URL` exigem HTTP(S), sem credenciais/query no URL; servidores
demo públicos são recusados. Isso não é autorização LGPD para enviar coordenadas
reais ao endpoint informado. Contrato/autorização do serviço continuam necessários.

## 3. Schema, startup e armazenamento

Não existe migrate, seed, backfill ou descarte no startup/release. As entradas
Docker/Procfile/PDM chamam `scripts.runtime`: settings de produção, checks, acesso a
PostgreSQL/cache/storage, migrations já atualizadas, manifesto dos estáticos legível
e identidade do artefato antes do `exec`. Falhas saem sem refletir
URLs/credenciais/exceções. ASGI usa
`CONN_MAX_AGE=0`; o worker fecha conexões antigas por ciclo.

**Somente após autorização para um banco novo/vazio e configuração fictícia ou
homologação autorizada**, a sequência de referência é:

```sh
# ENV_FILE e PROJECT devem apontar exclusivamente para o ambiente autorizado.
docker compose --env-file "$ENV_FILE" -p "$PROJECT" config --quiet
docker compose --env-file "$ENV_FILE" -p "$PROJECT" build web
docker compose --env-file "$ENV_FILE" -p "$PROJECT" up -d db redis
# Operação explícita e separada: nunca aplicar no banco habitual por seguir o exemplo.
docker compose --env-file "$ENV_FILE" -p "$PROJECT" run --rm --no-deps web python manage.py migrate --noinput
docker compose --env-file "$ENV_FILE" -p "$PROJECT" run --rm --no-deps web python -m scripts.runtime release
docker compose --env-file "$ENV_FILE" -p "$PROJECT" up -d web proxy
# Só após cadastrar/aprovar a empresa e escolher seus limites/ID explicitamente:
docker compose --env-file "$ENV_FILE" -p "$PROJECT" up -d worker
```

Os guards `organizations.0002_retire_legacy`/`router.0003_retire_legacy` bloqueiam
dados antigos, não os convertem. `router.0004_automation_schedule` é incremental.
Nunca usar `--fake`, editar migrations aplicadas ou esvaziar tabelas para contornar
o bloqueio. Bancos anteriores à base UUID são incompatíveis.

Volumes separados para PostgreSQL, mídia e `/srv/private-documents` (UID 10001,
pasta 0700). Documentos devem ficar em caminho absoluto, fora de mídia, estáticos
e frontend; download continua autorizado pelo backend. Não publicar o volume por
NGINX/CDN. O probe de escrita não comprova que o volume seja durável no provedor.
Dimensionamento, criptografia em repouso, cotas e política de acesso precisam de
validação da infraestrutura escolhida.

## 4. Worker e observabilidade

Cada processo atende **uma empresa explícita**, revalidada a cada ciclo; não descobre
substitutos nem publica viagens. Configuração por grupo no banco, via ação
`automation/`, continua opt-in e sem defaults de horizonte/lote/frequência. Lotes
operacionais, lease, tentativas, retry e poll são `WORKER_*` explícitos do ambiente;
ausência/valores inválidos impedem a partida. Réplicas podem disputar a mesma empresa
sob os locks testados em PostgreSQL. Supervisionar o processo; não usar Celery.

O worker fica em profile próprio: `up -d worker` o seleciona explicitamente. As
variáveis podem permanecer vazias durante a instalação inicial da API, sem um ID
empresarial inventado; o launcher recusa executar o worker até todas serem válidas.

SIGTERM/SIGINT solicitam saída após o trabalho corrente. Compose concede 60 s na
referência; ajustar junto dos limites externos/lease e carga medida. SIGKILL/queda
abrupta dependem do rollback/checkpoint e recuperação de lease, não de um finally
garantido. Falhas de domínio/banco encerram o processo com erro estático para o
supervisor recomeçar; configuração inválida não deve causar restart infinito sem alerta.

- `GET/HEAD /health/live/`: processo HTTP vivo, sem banco/cache. É a única exceção
  ao redirect HTTPS, para o probe interno; não contém dados/configuração.
- `GET/HEAD /health/ready/`: SELECT 1, cache efêmero e escrita/leitura temporária
  no diretório privado. 200 `ok` ou 503 `unavailable`, sem detalhes, `no-store`.
- `check_runtime`: também confere plano de migrations vazio e manifesto/revisão;
  recusa manifesto dos estáticos ausente, inválido ou sem leitura.
  `--backend-only` dispensa só o frontend para operação isolada do worker.
- Logs JSON por allowlist: estado genérico/status e, no worker, contagens/duração.
  Mensagens livres, request, headers, query, argumentos e tracebacks não são
  serializados. Access log Daphne é desativado; proxy registra só status/tempo/bytes.
  Não reativar logging bruto como solução de diagnóstico.
- Acompanhar processos/restarts, readiness, latência e falhas HTTP, jobs pendentes/
  esgotados, leases vencidos e `automation-status/` (última tentativa/conclusão/erro).
  O formatter mínimo deliberadamente não preserva mensagens/tracebacks arbitrários;
  diagnóstico adicional exige coleta controlada sem PII.

Retenção/rotação e acesso aos logs no provedor ainda precisam de decisão; o Compose
não configura um coletor ou uma política LGPD. Também não há expurgo automático de
histórico, avaliações, objetos ou documentos. Esses itens bloqueiam produção, não
justificam excluir registros ou inventar prazos.

## 5. Backup, restauração e rollback

O banco é a fonte autoritativa; Redis não é substituto de backup. Para um snapshot
coerente, interromper writers web/worker ou usar estratégia consistente comprovada,
guardar dump PostgreSQL e arquivos privados da mesma entrega, com manifesto/digests.
Aplicar acesso mínimo, criptografia e destino/retenção aprovados. Não incluir
backup, chave privada, dumps ou documentos na imagem/Git. Nenhuma rotina de backup
com dados reais foi configurada/executada nesta tarefa.

Restaurar primeiro em **outro banco vazio e outro volume privado**, nunca usar
`--clean`/drop sobre o habitual como teste. Conferir migrations/UUID/FKs, contagens,
hashes e download autorizado, além de isolamento de acesso; medir RPO/RTO antes de
definir SLA. O smoke abaixo ensaia dump/restore e arquivo privado só com dados fictícios.

Rollback deve trocar a imagem inteira identificada: HTML, chunks, estáticos e API
compatíveis. Retomar uma imagem antiga não reverte o banco. As retiradas legadas
são irreversíveis e não admitem rollback implícito para callers antigos; exigir
plano concreto/backup e autorização antes de qualquer restauração/mudança de schema.
Abas com chunks antigos e recuperação de erro precisam ser testadas com o Vue real;
assets continuam revalidáveis, sem cache imutável presumido.

## 6. Smoke local descartável

```sh
pdm run python -m scripts.test_runtime --confirm-fictitious
```

Requer Docker local por socket Unix e OpenSSL. Não instala Compose no host: executa
CLI/Compose em imagem oficial fixada por digest, com socket e diretório temporário
controlados. Usa projeto/DB/volumes novos, certificados locais, credenciais e
coordenadas fictícias; recusa contexto remoto e ignora `.env`/URLs herdados. Só remove
os próprios recursos. Imagens-base/cache de build podem permanecer; não usa prune.

O roteiro valida configuração Compose real, build do runtime, instalação limpa,
release-check, worker interrompido/retomado, TLS/WSS com cookies/CSRF/revogação,
SPA/estáticos mínimos, download autorizado, indisponibilidade/retomada de serviços,
dump/restore em novo banco e volume privado, e ausência de marcadores privados nos
logs. OSRM é substituído apenas na fixture; não envia coordenadas à rede.

Execução integrada aprovada em 2026-11-16: todas as fases acima passaram e os
recursos próprios foram removidos. O restore comparou contagens e SHA-256 do
documento, além de executar o preflight no banco/volume restaurados. Evidências de
testes e correções do build em [PLANEJAMENTO.md](PLANEJAMENTO.md), seção 14.3.

Mesmo aprovado, **não** comprova compilação Vue, navegador (inclusive cookies de
terceiros bloqueados), GPS em celular suspenso, provedor, backup externo ou deploy.
Esses aceites e as decisões de retenção/LGPD continuam abertos.
