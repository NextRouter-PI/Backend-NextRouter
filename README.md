# NextRouter — Backend

## Rodando em desenvolvimento

1. Crie o `.env` (se ainda não existir) e instale as dependências:
   ```bash
   python ./scripts/setup_env.py
   ```
2. Confira o `.env`:
   - `ALLOWED_HOSTS=localhost,127.0.0.1` — apenas nomes de host, **sem** `http://` e sem porta.
   - `DATABASE_URL` — deixe comentado para usar o SQLite. Só defina se houver um PostgreSQL rodando.
   - `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` — SMTP usado para enviar
     o código de verificação do cadastro. No Gmail, use uma *senha de app*. Sem `EMAIL_HOST`, o e-mail (com o código)
     é impresso no terminal do servidor.
3. Aplique as migrações e inicie o servidor:
   ```bash
   pdm run migrate
   pdm run dev
   ```

A documentação dos endpoints fica em <u>http://localhost:8000/api/doc/</u>.

## Testes

```bash
pdm run test
```
