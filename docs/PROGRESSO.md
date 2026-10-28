Atualize este arquivo ao concluir qualquer tarefa e antes de encerrar a sessão.

# Estado — revisão estática de 2026-10-28; commit-base `fa4a6ec`

**Nesta sessão:** somente leitura e documentação; **não executei testes, schema, lint ou serviços**. Último baseline executado em sessão anterior: 46/46 testes, `pdm run check`, `pdm run schema`, `pdm run lint` e `check-deploy` com variáveis fictícias passaram (`tests/test_schema.py::OpenApiContractTests`, `app/settings/prod.py::SECURE_SSL_REDIRECT`). Não trate esse baseline como cobertura das falhas abaixo.

## Quadro de recursos

| Recurso | Estado | Evidência e limite |
|---|---|---|
| Contas, cadastro por código, JWT e sessões | **Parcial** | `modules/accounts/api/views/auth.py::CustomTokenObtainPairView.post`, `modules/accounts/api/views/email_token.py::EmailTokenViewSet.reset_password`; ordem das validações diverge da decisão do dono. |
| Revisão de empresas e vínculos | **Parcial** | `modules/organizations/admin.py::CompanyAdmin.approve_companies`, `modules/organizations/mixins/is_approved.py::ApproveProfileMixin.approve`; aviso por e-mail pode falhar sem observabilidade suficiente. |
| Grupos, veículos e horários | **Parcial** | `modules/organizations/api/views/company_route_group.py::CompanyGroupRouteViewSet`, `modules/transport/api/views/vehicle.py::VehicleViewSet`, `modules/transport/api/serializers/company_route_schedule.py::CompanyRouteScheduleCreateSerializer.validate`; não há teste de carga/concorrência demonstrado. |
| Viagens e presença | **Parcial** | `modules/transport/api/views/travel.py::TravelViewSet.start` aplica lock; `modules/transport/api/serializers/confirm_passenger_route.py::ConfirmPassengerRouteCreateSerializer.create` pode reverter presença. |
| Localização REST/WS | **Parcial** | `modules/transport/services.py::save_travel_location` publica após commit; `modules/transport/consumers.py::TravelLocationConsumer._can_receive` revalida sessão/acesso; sem teste de conexão WS mapeado. |
| Trajeto, OSRM e worker | **Parcial** | `modules/transport/optimization.py::process_optimization`, `modules/transport/osrm.py::optimize_coordinates`, `modules/transport/management/commands/process_route_jobs.py::Command.handle`; serviço externo e claims concorrentes não verificados. |
| Objetos perdidos e avaliações | **Parcial** | `modules/transport/api/serializers/lost_item.py::LostItemPatchSerializer.validate` não valida transição; `modules/transport/api/serializers/driver_rating.py::DriverRatingCreateSerializer.create` não revalida presença no lock. |
| Uploads privados | **Parcial** | `modules/uploads/api/views.py::DocumentUploadViewSet.download` exige titular/staff; `modules/uploads/api/serializers/document.py::DocumentSerializer` expõe identificador em respostas autorizadas; sem testes próprios em `modules/uploads/tests/test_api.py`. |
| Aviso de aprovação | **Parcial** | `modules/organizations/mixins/is_approved.py::dispatch_approval_email_on_commit` submete pós-commit; entrega/erro do executor não comprovados. |
| API OpenAPI | **Completo quanto ao schema gerado, não ao comportamento de cada endpoint** | `tests/test_schema.py::OpenApiContractTests` exige warnings zero, tags e resumos; não cobre WebSocket em `modules/transport/consumers.py::TravelLocationConsumer`. |

Nenhum recurso acima é marcado **Não iniciado**: há implementação identificável em cada um. “Parcial” não equivale a falha comprovada de todas as operações.

## Problemas conhecidos

### Alta — bugs comprovados por leitura

1. **Presença reversível por entrada alternativa.** `modules/transport/api/serializers/confirm_passenger_route.py::ConfirmPassengerRouteCreateSerializer.create` executa `update_or_create` com `confirm` fornecido pelo cliente: `POST` com `false` sobrescreve uma presença `True`, ao contrário de `modules/transport/api/views/confirm_passenger_route.py::ConfirmPassengerRouteViewSet.confirm`, que só marca `True`. **Impacto:** perde-se a confirmação, e avaliações/relatos condicionados a ela podem ser negados. **Direção:** decidir se desfazer presença é permitido; alinhar os dois fluxos e testar o ciclo de vida.
2. **Código verificado depois da senha.** `modules/accounts/api/serializers/email_token.py::PasswordResetSerializer.validate_password` e `modules/accounts/api/serializers/user.py::UserCreateSerializer.validate_password` rodam antes da validação conjunta do código pelo DRF; `modules/accounts/api/views/email_change.py::EmailChangeViewSet.validate_code` testa senha antes de `check_email_token`. **Impacto:** contraria a ordem exigida pelo dono e pode devolver erro de senha sem código validado. **Direção:** validar código antes da regra de senha, preservando contagem de tentativas; testar código e senha inválidos simultaneamente.

### Média — fragilidades, com hipótese sinalizada

3. **Presença não revalidada na gravação de avaliação (risco concorrente, não reproduzido).** `modules/transport/api/serializers/driver_rating.py::DriverRatingCreateSerializer.validate` exige `confirm=True`, mas `modules/transport/api/serializers/driver_rating.py::DriverRatingCreateSerializer.create` só revalida status e duplicidade sob lock. **Impacto possível:** avaliação criada após presença ser desconfirmada entre validação e gravação. **Direção:** reconferir presença sob transação/lock e testar em PostgreSQL.
4. **Estado de objeto perdido sem transições definidas (regra a confirmar).** `modules/transport/api/serializers/lost_item.py::LostItemPatchSerializer.validate` permite, a atores autorizados, voltar de `returned` para `reported`. **Impacto possível:** custódia contraditória. **Direção:** perguntar se reabertura é permitida; só então definir transições e testes.
5. **Identificador de documento em resposta autorizada (revisão de minimização, não bypass comprovado).** `modules/uploads/api/serializers/document.py::DocumentSerializer` inclui `public_id`; `modules/uploads/api/views.py::DocumentUploadViewSet.download` controla o download. **Impacto possível:** exposição desnecessária de identificador em clientes autorizados. **Direção:** avaliar necessidade/uso no frontend antes de restringir contrato.
6. **Falha de submissão de aviso sem registro.** `modules/organizations/mixins/is_approved.py::dispatch_approval_email_on_commit` usa `except Exception: pass`. **Impacto:** aprovação persiste sem indício confiável de que o envio sequer foi submetido. **Direção:** logar tipo de falha sem PII e definir mecanismo observável de retry, se exigido.
7. **Concorrência do worker não verificada.** `modules/transport/optimization.py::claim_job` usa `select_for_update(skip_locked=True)`; SQLite não reproduz a semântica de PostgreSQL. **Impacto possível:** processamento concorrente incorreto não detectado em dev. **Direção:** testar claims/retries de múltiplos workers em PostgreSQL, sem assumir bug de produção.
8. **Caminho de atualização em massa pode deixar trajeto válido indevidamente (a confirmar).** `modules/transport/signals.py::passenger_address_changed` invalida após `post_save`, não após `QuerySet.update()`. **Impacto possível:** trajeto com endereços obsoletos se houver atualização em massa fora dos fluxos usuais. **Direção:** localizar callers de `update()` que alterem endereço/vínculo; invalidar explicitamente se necessário.

### Baixa — desempenho e dívida de contrato

9. **Possível N+1 na criação de presenças.** `modules/transport/api/views/travel.py::TravelViewSet._create_passenger_confirmations` itera `Passenger` e acessa `passenger.user` sem `select_related`. **Impacto:** uma consulta extra por aluno em grupo grande. **Direção:** medir consultas e carregar usuário junto se confirmado.
10. **Possível N+1 ao serializar empresas públicas.** `modules/organizations/api/serializers/company.py::CompanyListAndRetrieveSerializer.to_representation` monta campos aninhados antes de reduzi-los; `modules/organizations/api/views/company.py::CompanyViewSet.get_queryset` não pré-carrega documentos. **Impacto:** consultas evitáveis na listagem pública, sem vazamento de campos na resposta comprovado. **Direção:** medir consultas e evitar serialização desnecessária antes da filtragem.
11. **Tokens no corpo do login (dívida de contrato, não brecha demonstrada).** `modules/accounts/api/views/auth.py::CustomTokenObtainPairView.post` mantém `access`/`refresh` no corpo além dos cookies. **Impacto possível:** cliente pode manusear tokens onde não precisa. **Direção:** acordar com frontend antes de qualquer mudança incompatível.

## Próximas sessões (ordem sugerida)

1. Confirmar regra de desconfirmação; corrigir `modules/transport/api/serializers/confirm_passenger_route.py::ConfirmPassengerRouteCreateSerializer.create` e testar `POST`/`PATCH` com viagem agendada/em andamento.
2. Corrigir ordem código → senha em `modules/accounts/api/serializers/email_token.py::PasswordResetSerializer`, `modules/accounts/api/serializers/user.py::UserCreateSerializer` e `modules/accounts/api/views/email_change.py::EmailChangeViewSet.validate_code` sem perder contagem de tentativas.
3. Revalidar presença em `modules/transport/api/serializers/driver_rating.py::DriverRatingCreateSerializer.create`; testar corrida em PostgreSQL.
4. Decidir transições de `modules/transport/models/lost_item.py::LostItem.Status` e necessidade de `public_id` em `modules/uploads/api/serializers/document.py::DocumentSerializer` com o dono/frontend antes de mudar contratos.
5. Cobrir WS, OSRM e worker com testes de falha/concorrência (`modules/transport/consumers.py::TravelLocationConsumer`, `modules/transport/osrm.py::optimize_coordinates`, `modules/transport/optimization.py::claim_job`); não há Celery.
6. Medir N+1, revisar callbacks de e-mail e callers de atualização em massa antes de otimizar (`modules/transport/api/views/travel.py::TravelViewSet._create_passenger_confirmations`, `modules/organizations/mixins/is_approved.py::dispatch_approval_email_on_commit`, `modules/transport/signals.py::passenger_address_changed`).

**Rodapé:** revisão/auditoria estática em 2026-10-28; nenhum teste ou serviço executado nesta sessão; status de execução acima é histórico, não resultado novo.
