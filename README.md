# NextRouter — backend

API Django do NextRouter, com Daphne/ASGI para HTTP e WebSocket. Pode ser
desenvolvida separadamente do frontend Vue.

## Começar

Requer Python >=3.13 e PDM. Em `backend/`:

```sh
pdm install
pdm run dev
```

Acesse <http://127.0.0.1:8000/api/doc/> ou `/admin/`. O servidor não instala
dependências, aplica migrations, cria dados nem inicia o frontend.

O ambiente dev usa SQLite persistente em `dev.sqlite3`, cache e canais em
memória, sem PostgreSQL ou Redis. Não lê `.env` automaticamente. Para preparar
um **banco novo com dados fictícios**, confirme o destino e execute separadamente:

```sh
pdm run migrate
pdm run createsuperuser  # opcional
```

Não aplique migrations no banco habitual ou legado seguindo este exemplo.

## Frontend e rede local

Para HMR, inicie `npm run dev` em `../frontend/` e abra
<http://127.0.0.1:5173>. Para servir o Vue compilado pelo Django, execute
`npm run build:backend` no frontend, reinicie o backend e abra
<http://127.0.0.1:8000>. Sem build, a raiz retorna 404; a API continua disponível.

Para compartilhar em uma rede confiável, use `pdm run dev-lan <IPv4>` e,
para HMR, `npm run dev:lan` no frontend. Use dados fictícios: HTTP na rede pode
limitar GPS e renovação de sessão. Não exponha o servidor de desenvolvimento à Internet.

## Documentação

- [Desenvolvimento e ambientes](../OPERACAO.md) · [Build integrado](../BUILD_VUE.md)
- [Contrato da API](../CONTRATO_API.md) · [Plano e evidências](../PLANO_IMPLEMENTACAO.md)
- [Contexto do backend](../CONTEXTO_BACKEND.md) · [Frontend](../frontend/README.md)

Os guias ficam na raiz comum; solicite acesso se tiver apenas este repositório.
O fluxo simplificado recente ainda não foi validado por testes ou execução.
