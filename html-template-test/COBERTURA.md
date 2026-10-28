# Cobertura de Endpoints — `html-template-test/`

Lista completa de todos os endpoints HTTP e WebSocket descobertos no código do backend (`app/urls.py`, `app/api.py`, `modules/accounts/urls.py`, `modules/organizations/urls.py`, `modules/transport/urls.py`, `modules/uploads/urls.py` e `modules/transport/routing.py`).

## 1. Autenticação, Sessões, Códigos por E-mail e Usuários (`modules/accounts` + `registration/confirm/`)

| Método | URL | Papel / Permissão | Formato | Campos (Path / Query / Body) | Página |
|---|---|---|---|---|---|
| `GET` | `/api/csrf/` | Público (`AllowAny`) | JSON | Nenhum (define cookie `csrftoken` e retorna `csrfToken`) | `index.html`, `contas.html` |
| `POST` | `/api/login/` | Público (`AllowAny` + CSRF) | JSON | `email`, `password` | `index.html`, `contas.html` |
| `POST` | `/api/token/` | Público (`AllowAny` + CSRF) | JSON | `email`, `password` | `contas.html` |
| `POST` | `/api/refresh/` | Sessão c/ cookie `refresh_token` (+ CSRF) | JSON | Sem corpo (usa cookie `refresh_token`) | `index.html`, `contas.html` |
| `POST` | `/api/token/refresh/` | Sessão c/ cookie `refresh_token` (+ CSRF) | JSON | Sem corpo (usa cookie `refresh_token`) | `contas.html` |
| `POST` | `/api/me/logout/` | Qualquer (`AllowAny` + CSRF) | JSON | Sem corpo (revoga sessão atual e limpa cookies) | `index.html`, `contas.html` |
| `POST` | `/api/token/logout/` | Qualquer (`AllowAny` + CSRF) | JSON | Sem corpo | `contas.html` |
| `GET` | `/api/sessions/` | Autenticado (`IsAuthenticated`) | JSON | Sem parâmetros | `contas.html` |
| `DELETE` | `/api/sessions/{session_id}/` | Autenticado (`IsAuthenticated`) | JSON | Path: `session_id` (UUID) | `contas.html` |
| `POST` | `/api/me/revoke-sessions/` | Autenticado (`IsAuthenticated`) | JSON | Sem corpo | `contas.html` |
| `POST` | `/api/me/deactivate/` | Autenticado (`IsAuthenticated`) | JSON | Sem corpo | `contas.html` |
| `POST` | `/api/registration/request/` | Público (`AllowAny`) | JSON | `email` | `contas.html` |
| `POST` | `/api/registration/verify/` | Público (`AllowAny`) | JSON | `email`, `code` (6 dígitos) | `contas.html` |
| `POST` | `/api/registration/confirm/` | Público (`AllowAny`) | JSON | `type` (`passenger`, `driver`, `company`, `user`) + dados conforme o tipo | `contas.html` |
| `POST` | `/api/password-reset/request/` | Público (`AllowAny`) | JSON | `email` | `contas.html` |
| `POST` | `/api/password-reset/verify/` | Público (`AllowAny`) | JSON | `email`, `code` (6 dígitos) | `contas.html` |
| `POST` | `/api/password-reset/confirm/` | Público (`AllowAny`) | JSON | `email`, `code` (6 dígitos), `new_password` | `contas.html` |
| `POST` | `/api/email-change/request/` | Autenticado (`IsAuthenticated`) | JSON | `new_email` | `contas.html` |
| `POST` | `/api/email-change/verify/` | Autenticado (`IsAuthenticated`) | JSON | `code` (6 dígitos) | `contas.html` |
| `POST` | `/api/email-change/confirm/` | Autenticado (`IsAuthenticated`) | JSON | `code` (6 dígitos), `password` | `contas.html` |
| `POST` | `/api/email-tokens/send-email/` | Público (`AllowAny` / `IsAuthenticated` p/ `new-email`) | JSON | `email`, `token_type` (`new-user`, `new-password`, `new-email`) | `contas.html` |
| `POST` | `/api/email-tokens/verify-token/` | Público (`AllowAny`) | JSON | `email`, `code`, `token_type` (`new-user`, `new-password`, `new-email`) | `contas.html` |
| `POST` | `/api/email-tokens/reset-password/` | Público (`AllowAny`) | JSON | `email`, `code`, `password` | `contas.html` |
| `GET` | `/api/users/me/` | Autenticado (`IsAuthenticated`) | JSON | Sem parâmetros | `index.html`, `contas.html` |
| `PATCH` | `/api/users/me/` | Autenticado (`IsAuthenticated`) | JSON | `name`, `phone`, `birthday`, `cep`, `street`, `number`, `complement`, `neighborhood`, `city`, `state`, `profile_picture`, `email`, `password`, `current_password`, `code` | `contas.html` |
| `GET` | `/api/users/` | Admin (`IsAdminUser`) | JSON | Query: `page`, `page_size` | `contas.html` |
| `POST` | `/api/users/` | Admin (`IsAdminUser`) | JSON | `code`, `email`, `name`, `password`, `cpf`, `phone`, `birthday`, `cep`, `street`, `number`, `complement`, `neighborhood`, `city`, `state`, `profile_picture` | `contas.html` |
| `GET` | `/api/users/{id}/` | Admin (`IsAdminUser`) | JSON | Path: `id` | `contas.html` |
| `PUT` | `/api/users/{id}/` | Admin (`IsAdminUser`) | JSON | Path: `id`; Body: `code`, `email`, `name`, `password`, `cpf`, `phone`, `birthday`, `cep`, `street`, `number`, `complement`, `neighborhood`, `city`, `state`, `profile_picture` | `contas.html` |
| `PATCH` | `/api/users/{id}/` | Admin (`IsAdminUser`) | JSON | Path: `id`; Body parcial de usuário | `contas.html` |
| `DELETE` | `/api/users/{id}/` | Admin (`IsAdminUser`) | JSON | Path: `id` | `contas.html` |

## 2. Uploads e Empresas (`modules/uploads` + `modules/organizations`)

| Método | URL | Papel / Permissão | Formato | Campos (Path / Query / Body) | Página |
|---|---|---|---|---|---|
| `POST` | `/api/uploads/images/` | Público (`AllowAny`) | `multipart/form-data` | `file` (JPG/PNG até 5 MB) | `empresas.html` |
| `POST` | `/api/uploads/documents/` | Público (`AllowAny`) | `multipart/form-data` | `file` (PDF até 10 MB), `description` | `empresas.html` |
| `GET` | `/api/uploads/documents/{attachment_key}/download/` | Dono do documento (empresa/motorista) ou Admin (`IsAuthenticated`) | Binário (`application/pdf`) | Path: `attachment_key` (UUID) | `empresas.html` |
| `GET` | `/api/companies/` | Público (`AllowAny`, lista aprovadas; Admin vê todas) | JSON | Query: `trade_name`, `state_registration`, `user__name`, `page`, `page_size` | `empresas.html` |
| `POST` | `/api/companies/` | Público (`AllowAny`) | JSON | `user_data` (`code`, `email`, `name`, `password`, `cpf`, endereço...), `trade_name`, `legal_name`, `cnpj`, `state_registration`, `contact_phone`, `contact_email`, `cep`, `street`, `number`, `complement`, `neighborhood`, `city`, `state`, `articles_of_association_document`, `state_operating_license_document`, `certificate_of_good_stading_document` | `empresas.html` |
| `GET` | `/api/companies/{id}/` | Público (`AllowAny`, detalhes completos só p/ dono/admin) | JSON | Path: `id` | `empresas.html` |
| `PATCH` | `/api/companies/{id}/` | Dono da empresa (`IsUserOwner`) | JSON | Path: `id`; Body parcial: `trade_name`, `legal_name`, `state_registration`, `contact_phone`, `contact_email`, endereço, documentos, `user_data` | `empresas.html` |
| `DELETE` | `/api/companies/{id}/` | Dono da empresa (`IsUserOwner`) | JSON | Path: `id` | `empresas.html` |
| `GET` | `/api/companies/me/` | Empresa autenticada (`IsAuthenticated`) | JSON | Sem parâmetros | `empresas.html` |
| `PATCH` | `/api/companies/me/` | Empresa autenticada (`IsAuthenticated`) | JSON | Body parcial de empresa | `empresas.html` |
| `GET` | `/api/companies/me/stats/` | Empresa aprovada (`IsCompany`) | JSON | Sem parâmetros | `empresas.html` |

## 3. Grupos de Rota e Horários (`modules/organizations` + `modules/transport`)

| Método | URL | Papel / Permissão | Formato | Campos (Path / Query / Body) | Página |
|---|---|---|---|---|---|
| `GET` | `/api/company-route-groups/` | Público (`AllowAny`, grupos de empresas aprovadas) | JSON | Query: `name`, `company`, `page`, `page_size` | `grupos-horarios.html` |
| `POST` | `/api/company-route-groups/` | Empresa aprovada (`IsCompany`) | JSON | `name`, `common_cep` | `grupos-horarios.html` |
| `GET` | `/api/company-route-groups/{id}/` | Público (`AllowAny`) | JSON | Path: `id` | `grupos-horarios.html` |
| `PATCH` | `/api/company-route-groups/{id}/` | Empresa dona aprovada (`IsCompanyOwner`) | JSON | Path: `id`; Body: `name`, `common_cep` | `grupos-horarios.html` |
| `DELETE` | `/api/company-route-groups/{id}/` | Empresa dona aprovada (`IsCompanyOwner`) | JSON | Path: `id` | `grupos-horarios.html` |
| `GET` | `/api/route-schedules/` | Autenticado do grupo (`IsAuthenticated`) | JSON | Query: `route_group`, `page`, `page_size` | `grupos-horarios.html` |
| `POST` | `/api/route-schedules/` | Empresa aprovada (`IsCompany`) | JSON | `route_group`, `go_hour` (`HH:MM`), `return_hour` (`HH:MM`) | `grupos-horarios.html` |
| `GET` | `/api/route-schedules/{id}/` | Autenticado do grupo (`IsAuthenticated`) | JSON | Path: `id` | `grupos-horarios.html` |
| `PATCH` | `/api/route-schedules/{id}/` | Empresa dona aprovada (`IsCompany, IsScheduleOwner`) | JSON | Path: `id`; Body: `route_group`, `go_hour`, `return_hour` | `grupos-horarios.html` |
| `DELETE` | `/api/route-schedules/{id}/` | Empresa dona aprovada (`IsCompany, IsScheduleOwner`) | JSON | Path: `id` | `grupos-horarios.html` |

## 4. Motoristas e Veículos (`modules/organizations` + `modules/transport`)

| Método | URL | Papel / Permissão | Formato | Campos (Path / Query / Body) | Página |
|---|---|---|---|---|---|
| `GET` | `/api/drivers/` | Autenticado (`IsAuthenticated`) | JSON | Query: `page`, `page_size` | `veiculos-motoristas.html` |
| `POST` | `/api/drivers/` | Público (`AllowAny`) | JSON | `user_data` (`code`, `email`, `name`, `password`, `cpf`, endereço...), `cnh` (`attachment_key` opcional) | `veiculos-motoristas.html` |
| `GET` | `/api/drivers/{id}/` | Autenticado (`IsAuthenticated`) | JSON | Path: `id` | `veiculos-motoristas.html` |
| `PATCH` | `/api/drivers/{id}/` | Próprio motorista ou Empresa dona (`IsUserOwner \| IsCompanyOwner`) | JSON | Path: `id`; Body: `user_data`, `cnh`, `route_group` | `veiculos-motoristas.html` |
| `DELETE` | `/api/drivers/{id}/` | Próprio motorista ou Empresa dona (`IsUserOwner \| IsCompanyOwner`) | JSON | Path: `id` | `veiculos-motoristas.html` |
| `GET` | `/api/vehicles/` | Autenticado do grupo (`IsAuthenticated`) | JSON | Query: `route_group`, `page`, `page_size` | `veiculos-motoristas.html` |
| `POST` | `/api/vehicles/` | Empresa aprovada (`IsCompany`) | JSON | `route_group`, `garage_cep`, `plate`, `model`, `year`, `capacity`, `status` (`active`, `maintenance`, `inactive`), `color`, `features` (array), `driver` | `veiculos-motoristas.html` |
| `GET` | `/api/vehicles/{id}/` | Autenticado do grupo (`IsAuthenticated`) | JSON | Path: `id` | `veiculos-motoristas.html` |
| `PATCH` | `/api/vehicles/{id}/` | Empresa dona aprovada (`IsCompany, IsVehicleOwner`) | JSON | Path: `id`; Body parcial de veículo | `veiculos-motoristas.html` |
| `DELETE` | `/api/vehicles/{id}/` | Empresa dona aprovada (`IsCompany, IsVehicleOwner`) | JSON | Path: `id` | `veiculos-motoristas.html` |

## 5. Passageiros e Vínculos na Rota (`modules/organizations`)

| Método | URL | Papel / Permissão | Formato | Campos (Path / Query / Body) | Página |
|---|---|---|---|---|---|
| `GET` | `/api/passengers/` | Autenticado (`IsAuthenticated`) | JSON | Query: `page`, `page_size` | `vinculos.html` |
| `POST` | `/api/passengers/` | Público (`AllowAny`) | JSON | `user_data` (`code`, `email`, `name`, `password`, `cpf`, endereço...) | `vinculos.html` |
| `GET` | `/api/passengers/{id}/` | Autenticado (`IsAuthenticated`) | JSON | Path: `id` | `vinculos.html` |
| `PATCH` | `/api/passengers/{id}/` | Próprio passageiro ou Empresa dona (`IsUserOwner \| IsCompanyOwner`) | JSON | Path: `id`; Body: `user_data`, `route_group` | `vinculos.html` |
| `DELETE` | `/api/passengers/{id}/` | Próprio passageiro ou Empresa dona (`IsUserOwner \| IsCompanyOwner`) | JSON | Path: `id` | `vinculos.html` |
| `PATCH` | `/api/passengers/{id}/request-route-group/` | Próprio passageiro (`IsUserOwner`) | JSON | Path: `id`; Body: `route_group` | `vinculos.html` |
| `PATCH` | `/api/passengers/{id}/approve/` | Empresa dona aprovada (`IsCompanyOwner`) | JSON | Path: `id` (sem corpo) | `vinculos.html` |
| `PATCH` | `/api/passengers/{id}/reject/` | Empresa dona aprovada (`IsCompanyOwner`) | JSON | Path: `id` (sem corpo) | `vinculos.html` |
| `PATCH` | `/api/drivers/{id}/request-route-group/` | Próprio motorista (`IsUserOwner`) | JSON | Path: `id`; Body: `route_group` | `vinculos.html` |
| `PATCH` | `/api/drivers/{id}/approve/` | Empresa dona aprovada (`IsCompanyOwner`) | JSON | Path: `id` (sem corpo) | `vinculos.html` |
| `PATCH` | `/api/drivers/{id}/reject/` | Empresa dona aprovada (`IsCompanyOwner`) | JSON | Path: `id` (sem corpo) | `vinculos.html` |

## 6. Trajetos e Otimização OSRM (`modules/transport`)

| Método | URL | Papel / Permissão | Formato | Campos (Path / Query / Body) | Página |
|---|---|---|---|---|---|
| `GET` | `/api/paths/` | Autenticado do grupo (`IsAuthenticated`) | JSON | Query: `route_group`, `page`, `page_size` | `trajeto-osrm.html` |
| `POST` | `/api/paths/` | Empresa aprovada (`IsCompany`) | JSON | `name`, `route_group`, `points` (lista JSON) | `trajeto-osrm.html` |
| `GET` | `/api/paths/{id}/` | Autenticado do grupo (`IsAuthenticated`) | JSON | Path: `id` | `trajeto-osrm.html` |
| `PATCH` | `/api/paths/{id}/` | Empresa dona aprovada (`IsCompany, IsPathOwner`) | JSON | Path: `id`; Body: `name`, `route_group`, `points` | `trajeto-osrm.html` |
| `DELETE` | `/api/paths/{id}/` | Empresa dona aprovada (`IsCompany, IsPathOwner`) | JSON | Path: `id` | `trajeto-osrm.html` |
| `POST` | `/api/paths/{id}/optimize/` | Empresa dona aprovada (`IsCompany, IsPathOwner`) | JSON | Path: `id`; Body: `passenger_ids`, `stops`, `start`, `end` (opcional), `async_mode` (opcional) | `trajeto-osrm.html` |
| `GET` | `/api/paths/{id}/optimization/` | Empresa dona aprovada (`IsCompany, IsPathOwner`) | JSON | Path: `id` | `trajeto-osrm.html` |

## 7. Viagens e Confirmação de Presença (`modules/transport`)

| Método | URL | Papel / Permissão | Formato | Campos (Path / Query / Body) | Página |
|---|---|---|---|---|---|
| `GET` | `/api/travels/` | Autenticado participante/empresa (`IsAuthenticated`) | JSON | Query: `company`, `driver`, `path`, `status` (`scheduled`, `in_progress`, `finished`, `canceled`), `page`, `page_size` | `viagens-presenca.html` |
| `POST` | `/api/travels/` | Empresa aprovada (`IsCompany`) | JSON | `path`, `driver`, `vehicle` (opcional se motorista tiver 1 veículo ativo) | `viagens-presenca.html` |
| `GET` | `/api/travels/{id}/` | Autenticado participante/empresa (`IsAuthenticated`) | JSON | Path: `id` | `viagens-presenca.html` |
| `PATCH` | `/api/travels/{id}/start/` | Motorista designado (`IsAssignedTravelDriver`) | JSON | Path: `id` (sem corpo) | `viagens-presenca.html` |
| `PATCH` | `/api/travels/{id}/location/` | Motorista designado (`IsAssignedTravelDriver`) | JSON | Path: `id`; Body: `latitude`, `longitude`, `recorded_at` (opcional) | `viagens-presenca.html` |
| `PATCH` | `/api/travels/{id}/finish/` | Motorista designado (`IsAssignedTravelDriver`) | JSON | Path: `id` (sem corpo) | `viagens-presenca.html` |
| `PATCH` | `/api/travels/{id}/cancel/` | Empresa dona aprovada (`IsCompanyOwner`) | JSON | Path: `id` (sem corpo) | `viagens-presenca.html` |
| `GET` | `/api/confirmations/` | Autenticado participante/empresa (`IsAuthenticated`) | JSON | Query: `travel`, `user`, `confirm`, `page`, `page_size` | `viagens-presenca.html` |
| `POST` | `/api/confirmations/` | Passageiro aprovado no grupo (`IsAuthenticated`) | JSON | `travel`, `confirm` (`true` / `false`) | `viagens-presenca.html` |
| `GET` | `/api/confirmations/{id}/` | Autenticado participante/empresa (`IsAuthenticated`) | JSON | Path: `id` | `viagens-presenca.html` |
| `PATCH` | `/api/confirmations/{id}/confirm/` | Passageiro dono da confirmação (`IsConfirmationOwner`) | JSON | Path: `id` (sem corpo) | `viagens-presenca.html` |

## 8. Localização em Tempo Real via WebSocket (`modules/transport/routing.py`)

| Protocolo | Caminho | Papel / Permissão | Formato | Mensagens | Página |
|---|---|---|---|---|---|
| `WS` | `/ws/travels/{travel_id}/location/` | Autenticado via cookie `access_token` (Motorista envia e recebe; Passageiro aprovado e Empresa aprovada recebem) | JSON | Envio (motorista): `{"latitude": -26.919, "longitude": -49.066, "recorded_at": "..."}` / Recebimento: `{"type": "location", ...}`, `{"type": "error", ...}`, `{"type": "closed"}` | `ws-localizacao.html` |

## 9. Objetos Perdidos e Avaliações de Motoristas (`modules/transport`)

| Método | URL | Papel / Permissão | Formato | Campos (Path / Query / Body) | Página |
|---|---|---|---|---|---|
| `GET` | `/api/lost-items/` | Autenticado participante/empresa (`IsAuthenticated`) | JSON | Query: `travel`, `status` (`reported`, `found`, `returned`), `page`, `page_size` | `objetos-avaliacoes.html` |
| `POST` | `/api/lost-items/` | Participante com presença confirmada ou motorista de viagem encerrada (`IsAuthenticated`) | JSON | `travel`, `item_description` | `objetos-avaliacoes.html` |
| `GET` | `/api/lost-items/{id}/` | Autenticado participante/empresa (`IsAuthenticated`) | JSON | Path: `id` | `objetos-avaliacoes.html` |
| `PATCH` | `/api/lost-items/{id}/` | Autor, motorista ou empresa da viagem (`IsLostItemParticipantOrOwner`) | JSON | Path: `id`; Body: `item_description`, `status` (`reported`, `found`, `returned`) | `objetos-avaliacoes.html` |
| `DELETE` | `/api/lost-items/{id}/` | Autor do relato (`IsItemOwner`) | JSON | Path: `id` | `objetos-avaliacoes.html` |
| `GET` | `/api/driver-ratings/` | Autenticado participante/empresa (`IsAuthenticated`) | JSON | Query: `driver`, `travel`, `page`, `page_size` | `objetos-avaliacoes.html` |
| `POST` | `/api/driver-ratings/` | Passageiro que confirmou presença em viagem encerrada (`IsAuthenticated`) | JSON | `travel`, `driver` (opcional), `score` (`1` a `5`), `comment` | `objetos-avaliacoes.html` |
| `GET` | `/api/driver-ratings/{id}/` | Autenticado participante/empresa (`IsAuthenticated`) | JSON | Path: `id` | `objetos-avaliacoes.html` |

## 10. Documentação OpenAPI e Painel Admin (`app/urls.py`)

| Método | URL | Papel / Permissão | Formato | Descrição | Página |
|---|---|---|---|---|---|
| `GET` | `/api/schema/` | Público (`AllowAny`) | YAML / JSON | Schema OpenAPI 3 gerado pelo `drf-spectacular` | `index.html` |
| `GET` | `/api/doc/` | Público (`AllowAny`) | HTML | Swagger UI interativo | `index.html` |
| `GET` | `/api/redoc/` | Público (`AllowAny`) | HTML | Redoc UI | `index.html` |
| `GET` | `/admin/` | Admin (`is_staff=True`) | HTML | Painel administrativo Django (aprovação/recusa de empresas) | `index.html`, `empresas.html` |
