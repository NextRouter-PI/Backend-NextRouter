# Testes do backend

Ferramentas opt-in: não são etapa automática do desenvolvimento. Executar testes
Django cria/aplica migrations no banco de teste; confirme o escopo antes de rodar.

## Comandos

Execute em `backend/`, somente quando a validação estiver autorizada:

| Comando | Escopo |
|---|---|
| `pdm run test` | Python local, exceto regressão de estados históricos de migrations. |
| `pdm run test modules.accounts.tests` | Recorte Python por módulo/classe/método. |
| `pdm run test-migrations` | Guardas contra perda de dados ao retirar schema legado. |
| `pdm run test-html` | Testes Node do cliente HTML, separados da suíte Python. |

`pdm run test` usa `tests.settings`: não carrega `.env`, usa SQLite em memória,
cache/canais locais, e-mail em memória e arquivos temporários próprios. O hasher
rápido é exclusivo desse perfil. Não use esses settings em servidores.
Uma chamada direta a `manage.py test` precisa de `--settings=tests.settings` para
ter esse isolamento; o padrão de `manage.py` continua sendo desenvolvimento.

Os testes de domínio estão em `modules/*/tests/`; `tests/` cobre contrato,
artefato, entrega HTTP, configuração e ferramentas locais. Os casos de schema
legado continuam válidos: migrations antigas ainda possuem guardas de integridade.
Somente o caso com subprocessos que migram estados históricos tem a tag `migration`.

Concorrência PostgreSQL e comunicação Redis entre processos permanecem, mas são
ignoradas no perfil local. Exigem outro ambiente de teste explicitamente isolado;
SQLite/memória não substituem essa evidência.

## Navegador

`node scripts/test_html_browser.mjs --confirm-fictitious` é um smoke manual opt-in com
Node >=22 e Firefox. Ele prepara banco/perfil temporários e inicia processos;
nunca é chamado por `pdm run test` ou `test-html`. Não comprova o Vue real.
O smoke Vue fica em `../frontend/scripts/test_django_browser.mjs`.

O runner duplicado de estáticos e seus aliases foram retirados. Entrega/cache/404
continuam em `test_frontend.py`; o build Vue real continua no smoke separado.
Esta revisão foi estática, sem executar testes, builds, serviços ou migrations.
