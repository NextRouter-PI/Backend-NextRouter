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
