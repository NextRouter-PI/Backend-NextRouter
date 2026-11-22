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
