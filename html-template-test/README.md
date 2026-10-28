# `html-template-test/` — Páginas HTML para Teste Manual da API NextRouter

> **AVISO DE SEGURANÇA**: Esta pasta é uma ferramenta exclusiva para ambiente de desenvolvimento local. Não a exponha em produção, não a inclua em `STATIC_ROOT`/coleta de arquivos estáticos nem grave senhas, tokens ou segredos reais nos arquivos.

## 1. Como Servir e Abrir as Páginas

Em um terminal na raiz do repositório, inicie o backend Django/Daphne em modo de desenvolvimento (`http://localhost:8000`):

```bash
pdm run runserver 127.0.0.1:8000
```

Em outro terminal na raiz do repositório, sirva a pasta `html-template-test/` na porta `5173` (já liberada em `CORS_ALLOWED_ORIGINS` e `CSRF_TRUSTED_ORIGINS` no `app/settings/dev.py`):

```bash
python3 -m http.server 5173 --bind 127.0.0.1 --directory html-template-test
```

Abra no navegador:

```text
http://localhost:5173/index.html
```

*(Importante: use o mesmo host `localhost` tanto no navegador quanto na URL base da API `http://localhost:8000` para que o navegador compartilhe os cookies `csrftoken`, `access_token` e `refresh_token` com `SameSite=Lax`.)*

## 2. Como Configurar a URL Base e Fazer Login

1. Em `index.html`, confirme o campo **URL Base da API** (`http://localhost:8000` por padrão) e clique em **Salvar URL Base**.
2. Na seção **2. Sessão Atual e Troca Rápida de Papel**, digite o e-mail e a senha no formulário `POST /api/login/` (você pode clicar nos botões de preenchimento rápido de e-mail para Empresa, Motorista, Passageiro ou Admin caso tenha executado `python manage.py seed_demo_data`).
3. Ao autenticar:
   - O backend define os cookies HttpOnly (`access_token` e `refresh_token`) e o cookie `csrftoken`.
   - A página guarda o token de acesso (`nr_access_token`), o token CSRF (`nr_csrf_token`) e os dados de `/api/users/me/` no `sessionStorage` da aba.
   - Todas as páginas exibem no topo quem está logado e o papel atual (`company`, `driver`, `passenger` ou `admin`).
4. Para trocar de papel nas chamadas REST, autentique com outro usuário em `index.html` ou selecione uma sessão já autenticada no seletor **Alternar token Bearer salvo nesta aba**. Para o WebSocket (`ws-localizacao.html`), faça login diretamente no `POST /api/login/` com o usuário desejado para atualizar o cookie HttpOnly `access_token`.

## 3. Roteiro Sugerido de Teste Ponta a Ponta

1. **Cadastro e Aprovação da Empresa (`contas.html` + `empresas.html` + `/admin/`)**:
   - Em `contas.html`, envie `POST /api/registration/request/` com o e-mail da empresa e copie o código de 6 dígitos impresso no console do Django.
   - Em `empresas.html`, envie 3 arquivos PDF em `POST /api/uploads/documents/` para preencher os 3 campos `attachment_key` e envie `POST /api/companies/`.
   - Acesse `http://localhost:8000/admin/organizations/company/` como administrador e aprove a empresa (`is_approved=True`).
   - Faça login como a empresa em `index.html` e consulte `GET /api/companies/me/stats/` em `empresas.html`.
2. **Criação de Grupo de Rota, Horário, Motorista e Veículo (`grupos-horarios.html` + `veiculos-motoristas.html`)**:
   - Em `grupos-horarios.html`, crie um grupo em `POST /api/company-route-groups/` (anote o `id` do grupo) e crie um horário em `POST /api/route-schedules/`.
   - Cadastre ou autentique um motorista, solicite entrada no grupo em `vinculos.html` (`PATCH /api/drivers/{id}/request-route-group/`) e, autenticado como empresa, aprove-o (`PATCH /api/drivers/{id}/approve/`).
   - Em `veiculos-motoristas.html`, cadastre um veículo ativo vinculado ao grupo e ao motorista em `POST /api/vehicles/`.
3. **Pedido de Entrada do Passageiro e Aprovação (`vinculos.html`)**:
   - Autenticado como passageiro (ou após cadastrar um em `POST /api/passengers/`), envie `PATCH /api/passengers/{id}/request-route-group/` informando o `route_group`.
   - Autenticado como empresa dona do grupo, envie `PATCH /api/passengers/{id}/approve/`. Verifique no terminal do Django o disparo assíncrono do e-mail de aprovação pós-commit.
4. **Criação de Trajeto e Otimização OSRM (`trajeto-osrm.html`)**:
   - Autenticado como empresa, crie um trajeto em `POST /api/paths/` vinculado ao grupo.
   - Envie `POST /api/paths/{id}/optimize/` informando `passenger_ids` e/ou `stops`, `start` e `end`. Confira a melhor ordem (`order`), `distance_meters`, `duration_seconds`, `points` e `geometry`.
5. **Agendamento da Viagem e Confirmação de Presença (`viagens-presenca.html`)**:
   - Autenticado como empresa, crie a viagem em `POST /api/travels/` (`status = scheduled`).
   - Autenticado como passageiro aprovado do grupo, confirme presença em `POST /api/confirmations/` com `confirm = true` (repita o envio para verificar a idempotência).
6. **Início da Viagem e Localização em Tempo Real (`viagens-presenca.html` + `ws-localizacao.html`)**:
   - Autenticado como motorista designado, inicie a viagem em `PATCH /api/travels/{id}/start/` (`status = in_progress`).
   - Em `ws-localizacao.html`, conecte na **Parte 1 (Motorista)** e na **Parte 2 (Acompanhamento)** informando o `travel_id`.
   - Envie um ponto avulso ou inicie a **Sequência Simulada de Pontos** e observe as atualizações chegando em tempo real no painel de acompanhamento.
7. **Encerramento da Viagem (`viagens-presenca.html`)**:
   - Autenticado como motorista designado, envie `PATCH /api/travels/{id}/finish/` (`status = finished`).
   - Verifique em `ws-localizacao.html` o recebimento da mensagem `{"type": "closed"}` e o fechamento automático do WebSocket (`código 1000`).
8. **Relato de Objeto Perdido e Avaliação do Motorista (`objetos-avaliacoes.html`)**:
   - Autenticado como o passageiro que confirmou presença na viagem encerrada, relate um item em `POST /api/lost-items/` e avalie o motorista em `POST /api/driver-ratings/` (nota de `1` a `5`).
   - Autenticado como empresa ou motorista, atualize o status do objeto perdido em `PATCH /api/lost-items/{id}/` para `found` ou `returned`.

## 4. Limitações Conhecidas

- **WebSocket no Navegador e Cookies**: A API nativa `WebSocket` do navegador não permite enviar cabeçalhos `Authorization: Bearer` customizados; portanto, o canal `ws/travels/{travel_id}/location/` autentica sempre pelo cookie HttpOnly `access_token` do último login efetuado no navegador. Para testar motorista e passageiro simultaneamente em WebSocket, use duas janelas (normal + anônima/outro perfil de navegador) ou alterne o login em `index.html`.
- **Rate Limit de Localização**: O backend rejeita coordenadas enviadas com intervalo inferior a `LOCATION_MIN_INTERVAL_SECONDS` (padrão `2` segundos); na simulação de sequência do WebSocket, mantenha o intervalo em `>= 2500` ms.
- **Serviços Externos (OSRM e Nominatim)**: O endpoint `POST /api/paths/{id}/optimize/` exige que `OSRM_URL` e `GEOCODING_URL` estejam configurados no `.env` e acessíveis; caso o OSRM esteja indisponível, o backend retorna `503 Service Unavailable` sem sobrescrever o trajeto anterior.
