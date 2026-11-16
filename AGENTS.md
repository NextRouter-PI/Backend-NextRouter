# NextRouter — instruções para agentes

## Fonte de verdade e escopo

- Leia [PLANEJAMENTO.md](PLANEJAMENTO.md) antes de começar e atualize seu acompanhamento
  antes de encerrar. Ele substitui os antigos documentos de `docs/`.
- Para o artefato frontend, consulte [BUILD_VUE.md](BUILD_VUE.md). É um tutorial
  de preparação e integração planejada, não confirmação de suporte já implementado.
- A adaptação **ainda não está concluída**. A modelagem nova cobre 1.1–1.6,
  mas o caminho operacional continua legado (seção 11 do planejamento). Não
  confundir regras-alvo com o código atual; conferir arquivos e registrar diferenças.
- Leia a legenda inicial e a seção 3.4 do planejamento: fluxo principal aprovado
  não significa que todas as recomendações técnicas ou regras de exceção estejam
  aprovadas. Feche as pendências que bloqueiam a subetapa antes de implementá-las;
  avance no trabalho independente sem inventar decisões de produto.
- Frontend Vue em repositório separado, mas build servido pelo backend em produção,
  na mesma origem de API/admin/WS. Não planejar Vercel/BFF/cookies de terceiros como
  dependência. Não editar o outro repositório sem acesso e escopo autorizados.
- Nesta adaptação, o dono permite substituir a API e não exige preservar dados de
  desenvolvimento. Documentar o contrato e coordenar frontend; isso não autoriza
  apagar banco ou reescrever migrations aplicadas sem confirmação concreta.

## Stack e mapa

- Python >=3.13; Django >=6.0.7; DRF >=3.17.1; drf-spectacular >=0.30.0.
- PDM, Ruff e Django TestCase; Channels/Daphne ASGI. Worker por management command,
  **não Celery**. SQLite local opcional; PostgreSQL e Redis obrigatórios em produção.
- `app/settings/`, `app/api.py`, `app/urls.py`, `app/asgi.py`: configuração e entradas.
- `modules/accounts/`: identidade, JWT/sessões, códigos; label atual `authenticator.User`.
- `modules/organizations/`: empresas, perfis, aprovação e grupos.
- `modules/transport/`: serviços/horários, frota, viagens, trajetos, jobs e WS.
- `modules/uploads/`: documentos privados; `shared/`: endereços, erros e paginação.
- `tests/helpers.py`: helpers de API. `html-template-test/`: cliente legado local,
  nunca publicar ou incluir no build/coleta de estáticos.

## Arquitetura e regras obrigatórias

- Views finas: HTTP, serializers, permissões e querysets. Services transacionais
  compartilhados por API/admin/worker; models para regras locais e constraints.
- Não tratar `save()`/signals como garantia de banco: operações em massa podem
  ignorá-los. `save()` não chama `full_clean()` automaticamente.
- Pessoas escolhem participantes, endereços, motorista e veículo; OSRM calcula
  ordem/trajetória. Não implementar alocação/agrupamento automático não aprovado.
- Uma empresa ativa por aluno/motorista; aprovação empresarial separada de rotas.
  Resposta diária, pedido, alocação e embarque são conceitos distintos.
- Um grupo ativo por aluno na empresa; isso não limita retornos autorizados nem
  grupos do motorista. Um ciclo empresarial pendente ou ativo por perfil; só
  solicitar outra empresa após encerrar. Titular retira pedido pendente; titular
  ou empresa encerram vínculo, bloqueado durante participação operacional ativa.
- Modelos novos de vínculos, programação, dias, respostas/pedidos, viagens datadas,
  participantes/reservas, snapshots, convites e avisos ainda não têm escrita operacional.
  Admin novo é somente leitura; endpoints/GPS legados não recebem viagens datadas.
  Worker legado só processa jobs de Path, nunca jobs novos de snapshot.
  Não habilitar caminho novo mantendo API/admin/WS legados com outra fonte de verdade;
  substituição de callers e remoção do legado têm marco explícito no planejamento.
- Regeneração aprovada: automática somente para datas futuras não publicadas;
  publicadas exigem revisão explícita. Preservar respostas/decisões/histórico e
  cancelados. Conflitos preservam registros e geram pendência bloqueante até resolução
  explícita. Uma viagem publicada congela a regeneração automática de todo o grupo/data.
- Encerramento de vínculo/troca de grupo exige resolver antes alocações/designações
  futuras não canceladas/desistidas, além do bloqueio durante participação em andamento.
  Serviços novos ainda isolados dos callers; ver seção 12 do planejamento.
- Pedidos precisam ser aprovados antes do fim da prorrogação. Aprovação **não**
  transfere imediatamente: preserva escolha/alocação anterior até cálculo validado;
  proposta pode reservar capacidade. Aplicação revalida e transfere atomicamente.
  Falha de cálculo mantém o anterior. Não seguir a antiga receita de aceite que
  transferia antes de calcular. Publicação é por viagem; uma viagem por serviço/data
  nesta versão, sem viagens adicionais. Desistência por trecho invalida pedido conflitante.
- Política por grupo: prazo normal + prorrogação opcional com aceite manual.
  Desistência antes do embarque é permitida após prazo. Detalhes no planejamento.
- Preparar viagens a partir da configuração habitual não é escolher motorista por
  algoritmo. Copiar escolhas humanas é permitido; selecionar substitutos por
  heurística não. Aceite de pedido, cálculo e publicação são operações distintas.
- Isolar querysets por empresa/participação antes de filtros; permissões de objeto
  não protegem listas. Revalidar invariantes nos services, inclusive com concorrência.
- Alunos podem ser menores: não expor identidade, endereço ou localização sem
  necessidade/autorização. Não logar senha, código, JWT, CPF, endereço ou coordenadas.
- Código de confirmação deve ser validado antes das regras de senha; existem
  divergências atuais listadas no planejamento. Preservar tentativas e antienumeração.
- Produção-alvo: cookies HttpOnly/Secure e CSRF, mesma origem, sem JWT em JSON/storage/URL.
  Não desabilitar CSRF/CORS/origin checks para fazer a integração funcionar.
- CSRF não é JWT: seu token de bootstrap pode ser entregue ao Vue. Cookie de access
  precisa alcançar `/api/` e `/ws/`. CORS vazio não implica allowlist WS vazia.
- Novas FK de usuário usam `settings.AUTH_USER_MODEL`. URLs em inglês, mensagens em
  português, fuso America/Sao_Paulo com USE_TZ. Documentar OpenAPI e testar negações.

## Segurança de execução e validação

- Pergunte antes de criar/aplicar migrations, alterar settings/dependências ou
  executar operações destrutivas, salvo autorização explícita da tarefa para a ação.
- Nunca sobrescreva trabalho alheio, edite migration aplicada, descarte dados,
  exponha segredos ou faça push/merge sem pedido. Use banco temporário nos testes.
- `manage.py` usa dev; ASGI/WSGI usam prod por padrão. Dev lê `.env`; force variáveis
  de shell para não atingir serviços/dados reais:

```sh
export DATABASE_URL=sqlite:////tmp/opencode/nextrouter-dev.sqlite3
export REDIS_URL=
export GEOCODING_URL=
export OSRM_URL=
export EMAIL_HOST=
pdm run test
pdm run lint
pdm run check
pdm run schema
```

- Rode baseline antes de implementação e validações pertinentes após cada mudança.
  Registre o que não foi executado. PostgreSQL para concorrência; Redis para múltiplos
  processos. SQLite não comprova locks. Não inicie worker com dados reais.
- Em mudanças exclusivamente documentais, verificar links, consistência, blocos e
  `git diff --check`; não repetir testes funcionais já aprovados sem alteração ou
  dúvida nova. Não apresentar um baseline anterior como executado na revisão atual.
- A autorização para executar uma subetapa deve explicitar as mudanças previstas
  de schema/settings/dependências. Pergunte uma vez pelo conjunto concreto, não a
  cada chamada já autorizada; autorização para documentar não autoriza implementar.
- `pdm run check` inclui makemigrations somente check/dry-run; `pdm run format`
  modifica arquivos. `check-deploy` exige variáveis obrigatórias: ver planejamento
  e `app/settings/prod.py`, sem gravar credenciais reais.

## Commits e documentação

- **Commits devem seguir o padrão já utilizado e ser realizados por mudança lógica.**
- Consulte `git log`; padrão predominante: `feat:`, `fix:`, `chore:` com descrição
  curta em português; use `docs:` para documentação.
- Inclua implementação, testes e documentação da mesma mudança no mesmo commit.
  Não junte assuntos independentes, trabalho alheio ou artefatos gerados indevidos.
- Atualize PLANEJAMENTO.md com progresso, decisões, evidências e limites reais.
  Não marcar etapa como concluída apenas porque existem tabelas ou schema válido.
