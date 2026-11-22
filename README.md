# NextRouter — backend

API Django do NextRouter, com Daphne/ASGI para HTTP e WebSocket.

## Começar

Requer Python >=3.13 e PDM. Em `backend/`:

```sh
pdm install
pdm run dev
```

Acesse <http://127.0.0.1:8000/api/doc/> ou `/admin/`. O servidor não instala
dependências, aplica migrations nem cria dados.

Por padrão, dev usa SQLite persistente em `dev.sqlite3`, cache e canais em
memória. Se existir, `backend/.env` é carregado: valores preenchidos prevalecem
sobre o terminal e podem ativar serviços externos (como um banco PostgreSQL no
Supabase quando `SUPABASE_DATABASE_URL` ou `DATABASE_URL` é informada). Confira
o destino antes de iniciar.
Para preparar
um **banco novo com dados fictícios**, confirme o destino e execute separadamente:

```sh
pdm run migrate
pdm run createsuperuser  # opcional
```

Não aplique migrations no banco habitual ou legado seguindo este exemplo.

## Comandos principais

| Comando | Descrição |
|---|---|
| `pdm run dev` | Inicia o servidor ASGI em `127.0.0.1:8000` (`app.settings.dev`). |
| `pdm run dev-lan <IPv4>` | Inicia o servidor na rede local confiável autorizando o IPv4 informado. |
| `pdm run worker` | Inicia o worker de rotas e agendas para todas as empresas aprovadas (com defaults automáticos). |
| `pdm run simulate-trip` | Prepara o cenário fictício local e simula uma viagem com GPS via WebSocket (`--reset-db` opcional). |
| `pdm run prod-build` | Produção (Render/PaaS): executa `collectstatic` e `migrate` com `app.settings.prod`. |
| `pdm run prod-web` | Produção (Render/PaaS): valida o runtime e inicia o Daphne na `$PORT` (padrão `8000`). |
| `pdm run prod-worker` | Produção (Render/PaaS): inicia o worker em produção com defaults seguros. |

No **Render** (ou qualquer PaaS com `pip` nativo, sem precisar instalar `pdm`):
- **Build Command:** `pip install . && python -m scripts.runtime build`
- **Start Command (Web):** `python -m scripts.runtime web`
- **Start Command (Worker):** `python -m scripts.runtime worker`

## Rede local

Quando `frontend_dist/` está presente, o Django serve os arquivos estáticos na
raiz (<http://127.0.0.1:8000>); sem artefato compilado, a raiz retorna 404 e a
API continua disponível.

Para compartilhar o servidor em uma rede local confiável, use
`pdm run dev-lan <IPv4>`. Use dados fictícios: HTTP na rede pode limitar
recursos que exigem contexto seguro. Não exponha o servidor de desenvolvimento à Internet.

## Documentação

- [Testes opt-in e isolamento](tests/README.md)
- [Instruções para agentes](AGENTS.md)
