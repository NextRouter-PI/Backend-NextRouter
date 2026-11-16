# NextRouter — planejamento de adaptação

**Decisões aprovadas em novembro de 2026; registro em 2026-11-15.**

Este é o documento principal de produto, arquitetura-alvo e execução da adaptação.
Para preparar os arquivos compilados do frontend, consulte o tutorial separado
[BUILD_VUE.md](BUILD_VUE.md).
Substitui `docs/DOMINIO.md`, `docs/ARQUITETURA.md`, `docs/DECISOES.md`,
`docs/CONVENCOES.md` e `docs/PROGRESSO.md`. Distinguir sempre **decisão aprovada**,
**proposta técnica a detalhar** e **comportamento já implementado**.

**Estado:** cobertura estrutural das subetapas **1.1–1.6** implementada e testada
no conjunto autorizado; ver seção 11. Etapa 0 ainda tem exceções pendentes.
Não declarar conclusão integral da transição: os callers/campos legados necessários
permanecem até as Etapas 2/3. Ainda sem ativação operacional do domínio novo.
A API/admin legados ainda operam com o domínio anterior; o backend não serve o build Vue.
Etapa 2 iniciada pelos serviços isolados de solicitação/decisão/retirada de vínculo
(seção 12), ainda sem ativação operacional ou substituição dos callers.
Não interpretar exemplos de modelos, estados, caminhos ou serviços como código existente.

### Como interpretar este documento

- **Aprovado:** fluxo de programação habitual, resposta diária, políticas por grupo,
  prorrogação com aprovação manual, desistência permitida, motorista habitual e aceite
  de substituto, geração semanal, avisos internos, uma empresa por perfil e produção
  Vue/Django na mesma origem. Complementos de vínculo/grupo na seção 10.8 e decisões
  da continuação da Etapa 1 na abertura da seção 10 e na seção 11.
- **Orientação técnica:** nomes, decomposição de entidades, estados sugeridos,
  organização dos serviços, transações e layout de build. Podem ser refinados com
  justificativa, sem alterar o comportamento aprovado.
- **Pendente de decisão:** limites do produto não respondidos explicitamente estão
  na seção 3.4. Uma sugestão deste documento não é autorização para decidir pelo dono.
- O código é a evidência do comportamento **atual**; este plano é a especificação
  **alvo**. `AGENTS.md` disciplina execução; `BUILD_VUE.md` detalha apenas o artefato
  frontend. Se uma regra de negócio divergir entre documentos, corrigir a divergência
  usando a decisão registrada, em vez de escolher silenciosamente uma interpretação.
- Horários como 22h/06h/08h/12h/17h são exemplos configuráveis, não constantes globais.

## 1. Objetivo e limites

Adaptar o protótipo de gestão de transporte para uma operação previsível: programação
habitual, resposta diária do passageiro, alocação por viagem, revisão/publicação pela
empresa e tratamento explícito das exceções. O algoritmo de trajetos não substitui
as decisões da empresa.

- Backend Django; frontend Vue.js em outro repositório.
- **Produção na mesma origem:** Django entrega o HTML e os arquivos compilados do
  Vue, além da API, admin e WebSocket. O navegador executa o Vue; não haverá SSR
  como requisito desta adaptação.
- Não depender de Vercel, BFF, domínio próprio ou cookies de terceiros. A decisão
  final substitui a proposta anterior de frontend e API em sites diferentes.
- Provedor do backend ainda não escolhido. Mesmo em domínio do provedor, o acesso
  público será único: `/`, `/api/`, `/admin/`, `/ws/` e arquivos públicos.
- Perfis continuam sendo empresa, motorista, passageiro/aluno e moderador da plataforma.
  Passageiro é o próprio aluno, possivelmente menor; não presumir representação legal.
- Pessoas escolhem grupos, serviços, endereços, participantes, motorista e veículo.
  OSRM calcula ordem/trajetória das paradas escolhidas; não aloca motoristas nem
  decide agrupamentos geográficos automaticamente.
- Uma empresa ativa por passageiro ou motorista. Participação em grupos e serviços
  não se confunde com aprovação do vínculo empresarial.
- **Complemento aprovado nesta execução:** um único grupo ativo por aluno na
  empresa. Aluno/motorista só solicita outra empresa após encerrar o vínculo atual;
  não há pedido de troca para outra empresa enquanto o vínculo estiver ativo.
- Sem vínculo ativo, há no máximo um pedido empresarial pendente por perfil.
  O titular pode retirá-lo. Titular ou empresa podem encerrar vínculo ativo,
  mas o encerramento é bloqueado durante participação operacional em andamento.
- Não há produção nem necessidade de preservar dados atuais. O contrato da API
  pode ser substituído, documentando a transição e coordenando o frontend.
- Isso **não autoriza automaticamente** apagar bancos, reescrever migrations
  aplicadas, mudar dependências ou executar deploy. A estratégia concreta de banco
  novo/migrations será revisada e autorizada antes dessas operações.

## 2. Fluxo de referência: SuperTransporte

A SuperTransporte se cadastra, um moderador a aprova e ela passa a aparecer nas
consultas públicas. Contratos com alunos e motoristas são negociados por fora.
Ana pede vínculo com a empresa, que a aprova. Carlos, Beatriz e Rafael também são
aprovados como motoristas. Trocar uma pessoa de rota dentro da empresa não exige
aprovar novamente seu vínculo com a empresa.

A empresa cria o grupo de atendimento Faculdade A, com endereço comum completo,
e os serviços habituais: ida Norte antes das 08h, ida Sul antes das 08h, retornos
Norte e Sul às 17h e retorno compartilhado às 12h. Ela escolhe previamente os
participantes elegíveis, pontos, dias da semana, horários, veículos e motoristas.
Carlos atende Norte, Beatriz atende Sul e Rafael atende o retorno compartilhado.
A empresa verifica se o retorno compartilhado é viável em capacidade e duração;
o sistema não decide juntar bairros por conta própria.

Ana possui ponto habitual na residência, ida Norte e autorização para voltar às
12h ou às 17h. Alterar seu endereço pessoal não deve alterar silenciosamente o
ponto operacional. Mudanças de ponto de transporte são gerenciadas pela empresa.
A origem do veículo é explícita: Carlos o busca na garagem da empresa; Beatriz
o guarda em sua garagem. Deslocamento pessoal até buscar o veículo não é o mesmo
que deslocamento da viagem.

O sistema gera dias e viagens futuros a partir da programação semanal, sem
duplicações. A empresa pode cancelar uma data por imprevisto; a geração seguinte
não pode recriar esse atendimento cancelado. Feriados e calendário acadêmico
automáticos ficam fora da primeira versão.

Na noite anterior, o aluno responde uma vez por grupo e data. Ana informa ida e
retorno às 12h; Pedro informa ida e retorno às 17h; Luiza informa somente retorno
às 12h. Ida e retorno são independentes; um aluno não escolhe dois retornos para
o mesmo atendimento diário. Não responder é diferente de informar que não irá.
Somente serviços previamente autorizados podem ser escolhidos.

A política pertence ao grupo: por exemplo, respostas livres até 22h da véspera,
com prorrogação opcional até 06h do dia atendido. Faculdade B pode ter outra política.
Sem prorrogação, inclusões e trocas pelo aluno ficam bloqueadas após o prazo normal.
Com prorrogação, tornam-se pedidos para aprovação manual. Não há abertura manual
excepcional de prorrogação como requisito inicial; ela é configurada na política.
Os prazos são instantes completos, não apenas horas sem referência à data.

Carlos e Beatriz seguem suas escalas sem confirmação diária obrigatória. Motorista
habitual informa indisponibilidade; a empresa escolhe um substituto, que aceita
ou recusa convite com prazo. Ausência de resposta nunca significa aceite. O convite
não aceito é pendência bloqueante, inclusive para o retorno do meio-dia.

Ao fechar o prazo normal, o sistema prepara listas com base nas respostas válidas
e no mapeamento habitual definido pela empresa, valida capacidade e solicita o
cálculo. A empresa resolve pendências e publica a programação. Intenção de viajar
não significa assento garantido antes da alocação e publicação. Se faltarem lugares,
motorista ou percurso válido, o sistema aponta o problema; não exclui alunos nem
distribui entre novos veículos automaticamente.

Se Pedro pedir para mudar das 17h para 12h durante a prorrogação, mantém a alocação
anterior até a aplicação da troca. Aprovar no prazo reserva/prepara a alteração;
só após cálculo validado a transferência é aplicada atomicamente, sem dupla alocação.
Falha no cálculo preserva a alocação anterior. Se a programação já estiver publicada, a alteração gera revisão
e aviso; não deixa um percurso antigo marcado como atual. Uma desistência, ao
contrário de inclusão/troca, pode ser avisada após o prazo sem aprovação, antes
do embarque, e fica visível ao motorista e à empresa.

Carlos inicia manualmente a viagem ao sair com o veículo. Somente os autorizados
acompanham sua localização. Ele consulta as paradas e abre o próximo destino em
aplicativo de navegação, sem exigir navegação curva a curva dentro do protótipo.
Marca cada aluno como embarcado ou não compareceu; GPS próximo da casa não prova
embarque. Registra desembarques e finaliza. Às 12h os alunos alocados acompanham
Rafael desde seu deslocamento até a faculdade, antes do embarque coletivo, e depois
são entregues nas paradas. Às 17h os outros retornam nas rotas habituais.

Cancelamentos, convites, decisões, publicação e revisões geram avisos persistentes
consultáveis na aplicação. Push, SMS e e-mails operacionais ficam fora desta versão.
E-mails existentes de autenticação continuam necessários; não os confundir com avisos
operacionais. O envio atual de aprovação de vínculo deverá ser alinhado ao novo escopo.

## 3. Regras e invariantes de produto

### 3.1. Demanda, alocação e execução são registros diferentes

- **Resposta diária:** intenção do passageiro, escolha de ida/retorno e quando respondeu.
- **Pedido:** proposta de alteração, com autor, decisão, motivo e horários; não modifica
  a escolha vigente enquanto pendente.
- **Participação:** lugar efetivamente alocado na viagem, com desistência e eventos reais.
- **Embarque/desembarque:** evidência operacional, independente da resposta antecipada.
- Capacidade é medida pelos participantes alocados; não pelo total de aprovados do grupo.
- Não permitir duas alocações incompatíveis para o mesmo passageiro no atendimento.
- Não remover alguém já embarcado por uma operação comum de desistência.
- Um aluno não participa de dois grupos ativos na mesma empresa. Trocar seu grupo
  dentro dela preserva a aprovação empresarial; não cria vínculo com outra empresa.
- O motorista só inicia/finaliza a viagem designada e se estiver aprovado e apto.
  Empresa aprovada gerencia planejamento e cancelamento pré-início.

### 3.2. Prazos, publicação e revisão

- Respostas livres terminam no prazo normal; envio e aprovação de inclusão/troca
  terminam no fim da prorrogação, se habilitada. Pedido ainda pendente expira ali.
- Não aceitar inclusão/troca depois do início da viagem nem permitir que a empresa
  contorne o prazo por um PATCH genérico. Exceções futuras exigem regra explícita.
- Desistência continua permitida antes do embarque, inclusive com viagem ativa.
  Atualiza a lista e gera aviso; não exige recálculo global automático em movimento.
- Aceitar um pedido não significa concluir imediatamente uma chamada externa ou
  publicar o novo percurso. Validar/reservar capacidade e manter estado explícito
  de preparação; a proposta transacional está na seção 4.1. Não criar redistribuição
  automática de alunos sem lugar.
- Publicação depende de motorista apto, aceite do substituto quando necessário,
  veículo disponível com capacidade conhecida, participantes válidos e percurso atual.
- Separar estado do atendimento/respostas, planejamento, execução, pedido e convite.
  Enumerar transições e erros antes de implementar os enums definitivos.
- Guardar os prazos efetivos por data. Alterar a política habitual não reescreve dias
  preparados/publicados. Alterações de configuração futura precisam de regra de vigência.
- Uma nova versão não deve mudar silenciosamente a informação já publicada. Invalidar
  a prontidão quando necessário e notificar a revisão efetivamente disponibilizada.

### 3.3. Exceções e limites iniciais

| Evento | Tratamento |
|---|---|
| Sem resposta | Identificar como sem resposta; não incluir automaticamente. |
| Ninguém pediu um serviço | Sinalizar à empresa para cancelar e avisar; não confundir com falta de processamento. |
| Capacidade insuficiente | Bloquear alocação/publicação inválida; empresa reorganiza explicitamente. |
| Motorista indisponível | Empresa escolhe substituto; aceite obrigatório. |
| Veículo indisponível | Empresa escolhe outro apto e revalida o planejamento. |
| Pedido recusado/expirado | Preservar escolha e alocação anteriores; registrar decisão. |
| Aluno não aparece | Motorista registra não comparecimento; política de espera é definida pela empresa. |
| OSRM/geocodificação falha | Não inventar percurso nem liberar publicação com versão obsoleta. |
| GPS/rede indisponível | Mostrar última atualização e estado desatualizado; não fingir posição atual. |
| Dia cancelado | Preservar histórico, invalidar trabalhos pendentes e não recriar automaticamente. |

Não prometer pontualidade apenas com a duração do OSRM: considerar embarque,
margem e viabilidade na revisão empresarial. Trânsito em tempo real, restrições
avançadas de frota, otimização multi-veículo, alocação automática, mudanças livres
de ponto por viagem e tratamento automatizado de emergências ficam fora do MVP.
Não presumir que uma aplicação web envia GPS de forma contínua com celular bloqueado
ou aba suspensa; validar no dispositivo-alvo e informar essa limitação.

### 3.4. Decisões que a Etapa 0 deve fechar com o dono

Perguntar apenas quando a decisão afetar a próxima subetapa; avançar em trabalhos
independentes. Não tratar as recomendações abaixo como regras já aprovadas.

| Questão ainda não fechada | Recomendação a apresentar e impacto |
|---|---|
| Regeneração automática: conflitos com respostas/alocações existentes | Decidido: reaplicar automaticamente apenas a datas futuras não publicadas; publicadas só por revisão explícita. Preservar decisões/histórico/cancelamentos. Ainda detalhar resolução quando configuração nova torna resposta/alocação inválida e granularidade em dia parcialmente publicado, sem descartar pessoas silenciosamente. |
| Cancelamento do dia com alguma viagem já iniciada | Não cancelar retroativamente viagens ativas/finalizadas. Confirmar cancelamento apenas das ainda não iniciadas e indicação de cancelamento parcial. |
| Encerrar viagem com aluno ainda marcado como embarcado; erro de marcação | Definir correção auditada e regra de fechamento, sem fabricar desembarque automático. |
| Desaprovação/desativação durante viagem ativa | Encerramento comum de vínculo já foi decidido: bloquear durante participação operacional em andamento (seção 10.8). Ainda definir efeitos de desaprovação empresarial/desativação de conta, quem conclui a operação e acesso residual; não presumir que esse bloqueio resolve todos esses eventos. |
| Pesquisa pública por região/destino | Definir filtros mínimos (por exemplo, cidade atendida e destino), sem presumir busca por raio ou geocodificação pública. Aprovação cadastral não implementa descoberta geográfica. |
| Histórico, retenção, avaliações e objetos perdidos | Precisar acesso de ex-vinculados, tempo de retenção e elegibilidade por embarque/viagem finalizada; reabertura de objeto continua pendente. |

Detalhes técnicos a registrar na mesma etapa: horizonte de geração e frequência do
worker, limites de espera, margem de agenda e modelo de horário planejado; nenhum
valor numérico foi aprovado como padrão universal. Esses detalhes não justificam
introduzir módulos de folha de pagamento, contratos financeiros ou emergência.

## 4. Arquitetura de implementação

Manter os módulos existentes; evitar uma reestruturação geral sem necessidade.

| Camada | Responsabilidade |
|---|---|
| Banco | FK, unicidade, checks e integridade representável por constraints. |
| Models | Estrutura, propriedades, regras locais e transições locais quando apropriado. |
| Services | Casos de uso, transações, locks, autorização de domínio, estados entre entidades. |
| Serializers | Contrato e validação de entrada/saída; chamar serviços para escrita de negócio. |
| Views | Serializers, queryset autorizado, permissões, coordenação HTTP e resposta. |
| Admin | Formulários e ações que usam os mesmos serviços de escrita da API. |
| Worker | Agendamento e execução idempotente por serviços; não regras alternativas. |

`save()` não é trigger de banco: `update()`/`bulk_create()` podem ignorá-lo e signals;
`full_clean()` não é chamado automaticamente por `save()`. Não colocar cálculo HTTP,
envio de avisos, transações entre agregados ou decisões operacionais ocultas nesses
hooks. Usar invalidação explícita e constraints onde couber. Não assumir que uma
validação de serializer impede corrida concorrente.

Serviços devem ser organizados por assunto (vínculos, programação, respostas,
planejamento, execução), sem concentrar tudo em um único `services.py`. API, admin
e worker compartilham esses caminhos. Publicação WS e outras entregas externas
ocorrem após commit; avisos persistentes são gravados atomicamente com a decisão.

### 4.1. Receita técnica para alteração e publicação

Decisão complementar: preservar escolha/alocação anterior até cálculo validado;
aprovação é distinta de aplicação. Não manter transação aberta durante OSRM.

1. Serviço recebe ator, ID do pedido e revisão esperada; não depende de `request`
   ou `Response` do DRF. Reobtém objetos do banco e valida autorização de domínio.
2. Na transação, bloqueia pedido, participação e viagens envolvidas em ordem
   consistente. Revalida elegibilidade, prazo, execução e capacidade atual.
3. Aprovação registra decisão e reserva de capacidade proposta, sem remover a
   participação anterior nem alterar escolha vigente. Reserva não é embarque nem
   segunda alocação efetiva; deve ser contada para não prometer o mesmo assento.
4. Grava proposta de revisão e jobs com entradas congeladas. Falha mantém a
   alocação anterior; aprovação e aplicação têm estados separados e auditáveis.
5. Worker calcula fora dos locks. Na gravação, verifica revisão, estado, cancelamento
   e titularidade do processamento; descarta resultado obsoleto. Falha gera pendência
   observável, nunca sucesso nem reconstrução usando dados atuais de outra revisão.
6. Com cálculo válido, serviço revalida e aplica escolha, transferência e revisões
   atomicamente, consumindo a reserva. Repetição não duplica efeito/aviso.
7. Empresa publica cada viagem pronta independentemente; grava aviso. `start` exige que
   revisão publicada, revisão atual e percurso pronto sejam compatíveis. Enquanto
   houver revisão pendente, uma publicação anterior não autoriza iniciar a viagem.

Manter histórico da publicação anterior com rótulo de desatualizada; não mostrá-la
como instrução vigente. Transferências e alterações de percurso estão bloqueadas
em viagens já iniciadas. Desistência em viagem ativa atualiza a lista de execução
e pode pular parada sem ninguém a atender, sem editar retroativamente o snapshot
nem invalidar a viagem em curso como se precisasse ser iniciada novamente.

### 4.2. Estados separados e geração determinística

Mapa conceitual para fechar na Etapa 0 (não impõe nomes de enums):

| Eixo | Estados/conceitos a distinguir |
|---|---|
| Janela de respostas | Ainda não aberta, normal, prorrogação, encerrada; calculada por prazos e cancelamento. |
| Atendimento por data | Ativo/cancelado e motivo; não usar somente ausência de viagens para representar cancelamento. |
| Pedido | Pendente, aceito, recusado, retirado, expirado/substituído. |
| Planejamento | Rascunho, preparando, com pendência, pronto; revisão publicada em campo/relação separado. |
| Execução | Não iniciada, em andamento, finalizada, cancelada antes do início. |
| Participação | Alocada, desistiu, não compareceu, embarcou, desembarcou; eventos auditáveis. |
| Convite | Pendente, aceito, recusado, expirado, substituído/revogado. |

- “Uma resposta diária” significa um registro lógico editável no período normal,
  não uma única submissão irreversível. Não exigir vínculo com viagem já publicada
  para responder; a demanda antecede a alocação.
- Copiar motorista, veículo e serviços habituais para a programação gerada **não é
  escolher automaticamente**: é executar a configuração humana. Se forem inválidos,
  registrar pendência, sem procurar substituto ou veículo por heurística.
- Destino comum, serviço (sentido/horário/semana), viagem datada e percurso geométrico
  são diferentes. Não reutilizar `Path` para representar todos eles nem criar uma
  tabela extra para cada substantivo sem necessidade de identidade/ciclo de vida.
- Sugestão de limite temporal: `agora < prazo` permite a operação; `agora >= prazo`
  encerra. Confirmar/documentar no contrato e testar igualdade e virada de data.
- Guardar elegibilidade ou seu histórico para saber quem era esperado naquele dia;
  “sem resposta” não pode mudar retroativamente ao incluir novo aluno no grupo.
- Geração usa chave única `(grupo, data)` e no máximo uma viagem por serviço nesse
  dia. Viagens adicionais para o mesmo serviço/data **não foram aprovadas nesta versão**.
- Regeneração reaplica configuração automaticamente apenas aos dias futuros não
  publicados, preservando respostas, decisões e cancelamentos. Publicados exigem
  revisão explícita; viagens iniciadas/passadas não são reescritas.
- Cancelamento de data futura deve existir mesmo antes de suas viagens serem geradas.
  Geração consulta esse registro e nunca usa um `update_or_create` que zere decisões.

### 4.3. Serviços, snapshots e testes: orientações práticas

- Proposta de módulos: regras de vínculo em `organizations/services/`; programação,
  respostas, planejamento e execução em `transport/services/`. Ao converter o atual
  `transport/services.py` em pacote, migrar imports/callers no mesmo commit; não deixar
  arquivo e pacote homônimos coexistindo. Não há exigência de framework de services.
- Models validam dados locais; services fazem escrita autorizada e transacional;
  serializers e formulários traduzem erros. Evitar service retornar resposta HTTP
  ou conhecer o admin. Adotar códigos de erro estáveis para conflitos, prazo e permissão.
- Constraints não fazem comparação arbitrária entre tabelas: ownership e capacidade
  precisam também de validação sob lock. Documentar uma ordem global dos locks por
  tipo/ID, inclusive start, aceite e publicação, para não introduzir deadlocks.
- Snapshots guardam apenas dados operacionais necessários. Alterar endereço/configuração
  não muda uma viagem passada; snapshot não é autorização para reter PII indefinidamente.
- Jobs precisam de revisão de entrada e identificação da tentativa/claim; um worker
  antigo que termina após timeout não pode gravar sobre o novo. Definir deduplicação
  para jobs e avisos, tentativas máximas e recuperação de tarefas abandonadas.
- Publicação de aviso é persistência interna; marcar “lido” é uma operação distinta.
  Consulta periódica paginada é suficiente para o MVP. WS de notificações separado
  não foi solicitado. “Lembrete” no exemplo não promete push com aplicativo fechado.
- Testar services sem HTTP, permissões por HTTP e admin, relógio controlado para
  prazos, e falhas externas simuladas. Concorrência usa conexões/transações realmente
  distintas em PostgreSQL, não apenas duas chamadas sequenciais no mesmo TestCase.
- Refresh e logout devem ser testados com cookies/CSRF reais; testes que só injetam
  autenticação não verificam o contrato do navegador.

## 5. Trilha por camadas, com marcos

As etapas seguem a preferência por camadas, não por funcionalidades completas.
Cada subetapa é pequena, testada, documentada e commitada por mudança lógica.
Não deixar imports/admin/schema quebrados entre marcos nem antecipar toda a API
antes das regras. Configurações indispensáveis podem entrar antes da Etapa 4.

“Por camadas” não significa apagar todos os modelos antigos de uma vez. Dentro de
uma subetapa, adicionar a estrutura nova, ajustar dependentes e remover a antiga
somente quando os callers forem tratados. Se coexistência temporária for necessária,
registrar um único caminho de escrita autoritativo e o marco de remoção; não manter
dois domínios divergentes. Permitir adaptações mecânicas de serializers/admin nas
Etapas 1/2 para manter o projeto carregável, sem antecipar regras ainda pendentes.

### Etapa 0 — Especificação e preparação da transição

1. Inventariar modelos, API/admin, permissões, WS, signals, jobs, uploads, avaliações,
   objetos perdidos, estatísticas e clientes manuais afetados.
2. Fechar vocabulário da seção 2 e tabelas de transições: vínculo, respostas,
   preparação/publicação, execução, pedido, convite e paradas.
3. Desenhar ER e catálogo de entidades/campos/constraints, com ownership, exclusão,
   histórico, nulabilidade e timestamps. Nomes abaixo são propostas, não schema final.
4. Precisar dias da semana, chegada desejada na ida versus partida da volta,
   referência da véspera, horizonte curto de geração e cancelamento de datas.
5. Definir conflitos de agenda com duração/margem de deslocamento: não tratar apenas
   viagens já em andamento nem inventar precisão que o tempo de OSRM não fornece.
6. Registrar contrato de mesma origem: cookies, CSRF, renovação, cache, SPA e arquivos.
7. Coordenar a substituição do contrato com o frontend separado; preparar mapa de
   endpoints antigos para novos recursos e ações, sem uma camada legada indefinida.
8. Inspecionar migrations e confirmar estratégia para banco novo antes de criar,
   aplicar, reconstruir migrations ou descartar qualquer dado.
9. Rodar baseline seguro e registrar resultados reais e limitações.
10. Resolver as decisões da seção 3.4 que afetam modelagem e registrar a resposta
     do dono; não converter recomendações em “aprovado” apenas por criar as tabelas.

**Avanço registrado:** inventário, baselines e decisões na seção 10; cobertura
estrutural 1.1–1.6 e seus limites na seção 11. Não representa conclusão da Etapa 0
nem das regras operacionais de todos os eixos.

**Marco:** o fluxo SuperTransporte e as exceções têm representação sem contradições;
estados, decisões pendentes e contrato de integração estão explícitos. Documento
de planejamento registrado não significa que toda esta etapa esteja concluída.

### Etapa 1 — Consolidação da modelagem

#### 1.1. Organizações: perfis e vínculo empresarial

- Desacoplar `Passenger`/`Driver` do único `route_group` atual; representar empresa
  e revisão do vínculo independentemente dos grupos. Uma empresa ativa por perfil.
- Bloquear solicitação a outra empresa enquanto houver vínculo ativo; encerrá-lo
  primeiro, sem sobrescrever a empresa atual ao receber um pedido.
- No máximo um ciclo pendente ou ativo por perfil. Titular retira pedido pendente;
  titular ou empresa encerram vínculo, bloqueado durante participação em viagem
  em andamento conforme a seção 10.8.
- Preservar identidade do usuário e documentos; empresa encerra vínculo, não apaga
  conta ou histórico do aluno/motorista como se fossem dados de sua propriedade.
- Definir preservação das viagens passadas quando muda vínculo, grupo ou aprovação.

#### 1.2. Grupo, pontos e serviços programados

- Evoluir `CompanyRouteGroup` para atendimento a destino comum com endereço completo.
- Representar participação do passageiro no grupo, ponto habitual e serviços autorizados.
- No máximo um grupo ativo por aluno na empresa; mudança interna não reinicia a
  aprovação do vínculo empresarial. A restrição não limita retornos autorizados
  nem impõe grupo único ao motorista.
- Substituir `CompanyRouteSchedule` ida/volta por serviços independentes: sentido,
  dias, horário-alvo, motorista, veículo, origem/fim e configuração habitual de paradas.
- Guardar ida habitual e retornos permitidos, incluindo retorno compartilhado.
- Veículo pertence à empresa, não ao grupo; capacidade conhecida e positiva para operar.
  Garagem precisa de ponto operacional preciso, não apenas CEP.
- Alterar perfil pessoal não altera automaticamente ponto operacional aprovado.

#### 1.3. Política e atendimento por data

- Política por grupo: prazo normal, prorrogação opcional e prazo final.
- Dia de atendimento: grupo/data únicos, prazos efetivos, cancelamento e configuração
  relevante congelada ou versionada. Usar datetimes conscientes de fuso.
- Representar exceções de calendário para impedir regeneração de data cancelada.

#### 1.4. Demanda diária e solicitações

- Resposta única por passageiro/grupo/data; ausência de resposta distinguível de negativa.
- Ida e retorno independentes; opção de não utilizar cada trecho, com resposta temporal.
- Pedido com estado, alteração proposta, vínculo com resposta vigente, autor,
  decisão, revisor e horários. Impedir aprovação de proposta substituída.
- Substituir `ConfirmPassengerRoute`; não reaproveitar um booleano para toda a operação.

#### 1.5. Viagem concreta e participação

- Evoluir `Travel`: data/serviço de origem, horários planejados, motorista/veículo
  efetivos, planejamento/publicação, execução e versão.
- Permitir pendências de designação durante planejamento, mas proibi-las ao publicar/iniciar.
- Participação por aluno/viagem: alocação, desistência, embarque, não comparecimento,
  desembarque e horários reais. Constraints e services impedem duplicação incompatível.
- Preservar restrições de um motorista/veículo em uma viagem ativa; complementar
  com validação de agenda futura nos serviços.

#### 1.6. Percursos, convites e avisos

- Separar trajeto habitual de snapshot/versionamento do percurso concreto: origem,
  fim, paradas, geometria, distância, duração e data de cálculo.
- Paradas guardam ordem, participantes atendidos e execução; atender vários alunos
  no mesmo ponto não deve exigir viagens ou localizações artificiais duplicadas.
- Vincular `RouteOptimizationJob` à revisão e entradas do cálculo; resultado velho
  não sobrescreve novo nem altera história de outras viagens.
- Convites: viagem, motorista convidado, validade, aceite/recusa e substituição.
- Avisos: destinatário, tipo, recurso, criação e leitura; payload mínimo, sem PII
  desnecessária. Registro de decisões inclui autoria e tempo sem logar endereços.

**Marco:** banco novo isolado sobe com as relações/constraints revisadas; fixtures,
imports e admin coerentes; testes de modelagem cobrem estrutura e casos inválidos.
Ainda não é entrega funcional completa da operação.

### Etapa 2 — Consolidação das regras em services/serializers/models

#### 2.1. Vínculos e configuração

- Solicitar/aprovar/recusar/encerrar vínculo; autorizar grupos e serviços.
- Validar mesma empresa, aprovação e disponibilidade dos objetos relacionados.
- Mudanças habituais têm vigência explícita; não reescrevem execução passada.
- Admin usa os mesmos serviços; campos de estado/relacionamentos protegidos não
  podem ser alterados livremente contornando uma ação de domínio.

#### 2.2. Geração, respostas e fechamento

- Gerar horizonte curto de atendimento/viagens a partir da semana, de modo idempotente.
- Não recriar dias cancelados nem zerar respostas/viagens já geradas.
- Receber resposta única, validar elegibilidade e distinção sem resposta/não vai.
- Conferir prazo diretamente nos serviços em cada escrita. Worker atrasado não
  prolonga prazo nem autoriza uma confirmação inválida.
- Fechamento prepara alocações pelos serviços habituais escolhidos pela empresa,
  valida capacidade e enfileira cálculo. Nunca descartar excedentes silenciosamente.

#### 2.3. Prorrogação e desistência

- Bloquear inclusão/troca se não houver prorrogação ou se ela acabou.
- Pedido pendente ou aprovado em preparação conserva a escolha anterior. Aprovar
  no prazo valida/reserva vaga e prepara cálculo; não transfere imediatamente.
- Após cálculo validado, aplicar revalida pertencimento, agenda, estado, revisões
  e capacidade sob transação e transfere atomicamente. Recusa, expiração de pedido
  pendente e falha de cálculo preservam o anterior; não fazer rollback tardio oculto.
- Desistência antes do embarque é imediata e visível, mesmo após prazo e com viagem ativa.

#### 2.4. Planejamento/publicação e cálculo

- Publicar somente com os requisitos da seção 3 cumpridos; zero participantes é
  situação explícita para decisão, não erro inexplicável do algoritmo.
- Incluir deslocamento do veículo até a coleta comum na informação operacional.
- Calcular snapshot por revisão. Resultado obsoleto/cancelado não se aplica.
- Alteração relevante após publicação invalida a prontidão e gera revisão/avisos;
  detalhar transação de aceite e preparação para não prometer percurso pronto antes dele.
- Não chamar OSRM dentro de lock longo; comparar revisão e revalidar no commit.

#### 2.5. Substituição e execução

- Registrar indisponibilidade, convidar substituto escolhido e aceitar/recusar com prazo.
- Revogar convite anterior ao substituí-lo; não permitir aceite atrasado ou em duplicidade.
- Centralizar start/finish/cancel, embarque/ausência/desembarque e avanço de parada.
- Início revalida motorista, veículo, percurso atual, publicação, capacidade e conflitos.
- GPS serve acompanhamento; motorista registra eventos reais. Viagem encerrada
  limpa posição atual e fecha acesso ao acompanhamento em tempo real.

#### 2.6. Concorrência, auditoria e efeitos

- Testar disputa pelo último assento, transferência, aceite concorrente, start versus
  recálculo, publicação versus mudança e dois workers processando a mesma tarefa.
- Usar constraints + transações/locks em ordem definida; não confiar só em `.exists()`.
- Gravar avisos e decisão atomicamente. Broadcast somente após commit, sem substituir
  o aviso persistente. Falha de entrega WS não pode apagar a decisão.
- Retries idempotentes com observabilidade e sem dados sensíveis.

**Marco:** casos de uso testados sem HTTP, inclusive falhas e concorrência real em
PostgreSQL nos pontos críticos; admin/worker/API não possuem regras divergentes.

### Etapa 3 — API, permissões, admin e integração Vue de mesma origem

#### 3.1. Contrato e views finas

- Recursos para vínculos, grupos/serviços, programação diária, minha resposta,
  pedidos, publicação/revisão, convites, viagens/participantes e avisos.
- Ações explícitas para publicar, aprovar pedido, aceitar convite, iniciar/finalizar
  e registrar embarque. Não aceitar PATCH genérico de estados protegidos.
- Querysets sempre isolados antes de filtros/paginação; permissão de objeto não
  substitui controle de lista. Services também verificam invariantes de domínio.
- Serializer não aceita silenciosamente campos de revisão/propriedade indevidos.
- Definir erros, pendências, paginação e exemplos; documentar substituição de endpoints.

#### 3.2. Acesso e recursos dependentes

- Empresa gerencia sua operação; motorista vê suas viagens e convites; passageiro vê
  suas respostas, pedidos e viagens alocadas. Staff não recebe bypass de escrita implícito.
- Membro do grupo não vê todos os endereços, percursos e viagens por esse fato.
- Separar acesso histórico mínimo de posição ao vivo; fim de vínculo não deve reescrever
  a participação passada nem conceder acesso operacional atual.
- Atualizar avaliações e objetos perdidos conforme participação efetiva; decidir
  explicitamente transições de custódia/reabertura, sem inventar nova regra por acaso.
- Estatísticas por data e serviço concretos, não por `started_at` ou todos os horários
  do grupo. Atualizar filtros, admin, testes, helpers e clientes legados.

#### 3.3. Sessão e CSRF

- Consolidar JWT/sessões revogáveis em cookies HttpOnly + Secure na produção de
  mesma origem. Não devolver access/refresh em JSON nem guardar JWT no storage do Vue.
- Rever `SameSite` para o cenário same-origin (em princípio `Lax`), paths, duração
  e limpeza dos cookies; preservar sessão administrativa e validar fluxo completo.
- Endpoint de bootstrap CSRF; enviar token CSRF no cabeçalho de mutações, inclusive
  login, refresh e logout conforme contrato. Não desabilitar CSRF por usar JWT.
- O token CSRF pode ser exposto ao JavaScript pelo bootstrap; não é o JWT nem o
  segredo de sessão. A proibição de tokens no JSON refere-se a access/refresh.
- Cookies de autenticação devem ser host-only (sem Domain amplo). O path do access
  precisa cobrir API **e** `/ws/`; restringi-lo a `/api/` quebra WS. Limitar refresh
  exige considerar também logout/revogação; limpar com os mesmos atributos utilizados.
- Tratar expiração, refresh concorrente, rotação, múltiplas abas, revogação e logout.
  Definir comportamento de 401/403, sem loops infinitos de renovação.
- Bearer deixa de ser requisito do navegador. Decidir explicitamente se permanece
  para ferramentas; não manter dois contratos de autenticação por acidente.
- Corrigir ordem código de confirmação → regras de senha nos fluxos divergentes,
  preservando proteção contra tentativas e enumeração de contas.

#### 3.4. WebSocket

- Autenticar pelo cookie da mesma origem; não exigir Authorization customizado do
  cliente WebSocket nativo nem colocar tokens na URL. Ticket/BFF não é necessário.
- Validar Origin por lista explícita, sessão, expiração e participação/designação.
- Revalidar receptores, perda de vínculo, revogação, fim da viagem e reconexão após refresh.
- HTTPS/WSS, limites de frequência/payload, posições fora de ordem e sinal de desatualização.
- Testar com navegador e Redis real entre processos, além de testes unitários.

#### 3.5. Rotas da SPA, arquivos e contrato com frontend

- Proposta de artefato: `frontend_dist/`, contendo `index.html` e arquivos compilados;
  contrato de cópia/URL será implementado na Etapa 4 e documentado no tutorial.
- Reservar `/api/`, `/admin/`, `/ws/`, `/static/`, `/assets/` e downloads. O fallback
  HTML só atende navegação da SPA; API/arquivo inexistente continua erro, nunca 200 HTML.
- Usar URLs relativas de API e WS derivados do host atual. Permissões do frontend
  são conveniência visual; backend continua responsável pela segurança.
- HTML sem cache longo; assets com hash podem ser imutáveis. Nada de cache público
  para respostas autenticadas, posição, documentos ou respostas com cookies sensíveis.
- Evitar dupla renomeação incompatível entre assets com hash do build Vue e manifest
  do Django: escolher e testar uma estratégia, não copiar `dist` cegamente para `STATIC_ROOT`.
- Arquivos enviados pelos usuários não são assets do frontend. Documentos permanecem
  fora dos diretórios públicos; revisar tipo de conteúdo, download e uploads hostis.
- CORS não é necessário para a UI em produção. Desenvolvimento pode usar proxy local
  `/api` e `/ws`; não liberar `*` nem previews genéricos de provedores.
- Não derivar mais a allowlist de Origin do WS exclusivamente de CORS: CORS pode
  ficar vazio em produção enquanto a origem pública legítima deve continuar aceita
  no handshake. `ALLOWED_HOSTS` usa host; Origin/CSRF usam esquema e host/porta.
- Cabeçalhos contra XSS/clickjacking, política de conteúdo compatível com mapas/WS
  quando aplicável, limites de abuso e segredos fora do bundle público.

**Marco de código:** HTTP/admin/WS e contrato de integração testados, com assets
mínimos de teste quando o build real ainda não estiver disponível. Não declarar
integração Vue real validada com uma página de teste.

**Marco integrado, compartilhado com a Etapa 4:** build real em navegador na mesma
origem, inclusive com cookies de terceiros bloqueados; autenticação, CSRF, logout,
WS, downloads, isolamento e recarga da SPA testados. A Etapa 4 pode iniciar para
fornecer esse ambiente sem esperar este marco integrado. OpenAPI não substitui
testes comportamentais. Trabalho no repositório Vue exige coordenação.

### Etapa 4 — Ambiente, build e operação

1. Manter worker por management command, não adicionar Celery. Reaproveitar o padrão
   de jobs do banco para geração, fechamento, preparação, retry e recuperação.
2. Agendamento reentrante: depois de interrupção, processar pendências vencidas sem
   duplicar viagens/avisos nem aplicar snapshots obsoletos. Limitar horizonte e carga.
3. Escolher provedor com HTTPS/WSS, ASGI, worker persistente, PostgreSQL, Redis,
   armazenamento privado persistente e backups/restauração verificáveis.
4. Atualizar Docker/Compose/scripts PDM e documentar execução. Não colocar geração
   de dados demo ou descarte de dados no startup/release de produção.
5. Integrar build do frontend separado: revisão fixada, lockfile, compilação reproduzível,
   artefato identificado, publicação conjunta e rollback coerente de HTML/assets/API.
   Não executar servidor Vite dev/preview em produção.
6. WhiteNoise já existe e pode servir assets; implementar montagem do artefato sem
   expor arquivos de desenvolvimento. A estratégia final pode usar proxy/CDN no futuro,
   mantendo mesma origem pública. Atualizar testes e tutorial se o layout mudar.
7. Node é ferramenta de build; não precisa existir no runtime Python. Avaliar build
   multi-stage ou artefato de CI, sem instalar dependências novas implicitamente.
8. Separar parâmetros de infraestrutura (env) de políticas de atendimento (banco).
   Rever URLs antigas do frontend, hosts, cookies, CSRF, CORS e links de e-mail.
9. Configurar proxy TLS confiável: remover cabeçalhos forjados antes de confiar em
   `X-Forwarded-Proto`/IP. Rever HSTS/preload/subdomínios, não impor ao domínio inteiro
   de um provedor sem entender a topologia.
10. Proteger Redis/banco/storage; acesso de geocodificação/OSRM autorizado para dados
    de alunos. Sem servidores públicos de demonstração para coordenadas reais.
11. Logs/métricas de estado, latência e erros sem senhas, códigos, JWT, CPF, endereço
    ou coordenadas. Definir retenção, acesso e tratamento LGPD, inclusive para menores.
12. Atualizar seeds, exemplos e instruções de desenvolvimento em dados fictícios.
    `html-template-test/` nunca entra no build público; substituí-lo/adaptá-lo quando
    o contrato mudar, sem apagar ferramentas úteis antes da necessidade.

**Marco:** instalação limpa e reproduzível; API/SPA/worker sobem; persistência e
recuperação verificadas; testes PostgreSQL/Redis, lint, checks e schema passam;
smoke de HTTPS/WSS/proxy/storage feito no provedor escolhido.

## 6. Cenários de aceite final

1. Empresa aprovada; Ana e motoristas aprovados na empresa; mover rota não desfaz aprovação.
2. Ana escolhe ida + 12h, Luiza somente 12h e Pedro ida + 17h numa resposta diária cada.
3. Grupo A e grupo B usam políticas diferentes; véspera e data atendida são calculadas corretamente.
4. Sem resposta não é negativa. Dois retornos simultâneos são rejeitados.
5. Geração repetida não duplica nem altera dados já publicados; dia cancelado não reaparece.
6. Fechamento ocorre sem prorrogar prazo por atraso do worker; modo rígido bloqueia inclusão.
7. Prorrogação recebe pedidos, não confirma alterações automaticamente; envio/aceite
   respeitam os prazos definidos com o dono na seção 3.4.
8. Pedro mantém 17h até cálculo validado; aplicação transfere atomicamente; recusa/falha preservam 17h.
9. Duas aprovações disputam a última vaga sem ultrapassar capacidade.
10. Motorista habitual não confirma todo dia; substituto precisa aceitar convite vigente.
11. Publicação inválida por falta de motorista, capacidade ou percurso atualizado é bloqueada.
12. Cálculo antigo não sobrescreve revisão nova e falhas externas não inventam geometria.
13. Desistência tardia antes do embarque gera aviso; desistência comum após embarque é rejeitada.
14. Motorista registra embarque/ausência/desembarque; proximidade GPS não altera presença sozinha.
15. Ida e retorno compartilhado incluem os deslocamentos operacionais apropriados.
16. Outra empresa, aluno não alocado ou motorista não designado não acessam dados indevidos.
17. Sessão persiste sem cookies de terceiros, JWT não aparece no JSON/storage/URL/logs.
18. CSRF inválido, sessão revogada, WS de origem não autorizada e acesso indevido são rejeitados.
19. Fim da viagem encerra acompanhamento; reconexão/posição antiga têm comportamento explícito.
20. Recarga de rota Vue funciona; API/asset inexistente não recebe fallback HTML; docs privados não vazam.
21. Mudanças habituais/vínculo não reescrevem viagens passadas nem confundem estatísticas por data.
22. Worker interrompido se recupera sem duplicação; avisos persistem mesmo se broadcast falhar.
23. Segundo grupo ativo do mesmo aluno na empresa é rejeitado; troca de grupo preserva aprovação empresarial.
24. Aluno/motorista com vínculo ativo não solicita outra empresa; tentativa não muda o vínculo atual.
25. Segundo pedido empresarial pendente é rejeitado; retirada pelo titular impede aprovação posterior.
26. Encerramento por titular/empresa preserva identidade e histórico; participação operacional em andamento o bloqueia.

## 7. Convenções de implementação e validação

- Django TestCase/unittest e helpers em `tests/helpers.py`; não introduzir pytest ou
  outra biblioteca sem necessidade e autorização. Mocks para serviços externos.
- Novas relações com usuário usam `settings.AUTH_USER_MODEL`; o label atual é
  `authenticator.User`, apesar de o código morar em `modules/accounts/`.
- URLs em inglês, mensagens em português, `USE_TZ=True` e fuso `America/Sao_Paulo`.
- Manter paginação atual (`page`, `page_size`, `total_pages`, `results`, limite 100)
  salvo decisão de contrato documentada; filtros atuam sobre queryset autorizado.
- OpenAPI com tags, summaries, request/response reais, erros e exemplos fictícios;
  usar `shared/openapi.py`/drf-spectacular conforme os padrões existentes.
- Cada subetapa inclui testes felizes, negações, regressão, documentação e commit lógico.
  Concorrência exige PostgreSQL; SQLite não comprova semântica de locks/skip_locked.
- Não adiar segurança, testes ou atualização do admin para o último commit da camada.
- Consultar documentação atual das bibliotecas ao implementar; não confundir pseudo-schema
  deste plano com uma exigência de nome específico para todas as classes.

### Comandos existentes (executar da raiz, em ambiente isolado)

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

`pdm run check` inclui `makemigrations --check --dry-run`; não aplica migrations.
`pdm run schema` grava `/tmp/opencode/nextrouter-schema.yaml`. O dev lê `.env`, mas
as variáveis do shell prevalecem. `manage.py` usa dev; ASGI/WSGI usam prod por padrão.
Não iniciar worker em dados reais. `pdm run format` altera arquivos, não é validação
somente leitura. `pdm run check-deploy` exige ambiente fictício completo ou ambiente
de homologação autorizado; nunca registrar valores reais neste documento.

### Infraestrutura atual a preservar/revisar

Stack: Python >=3.13, Django >=6.0.7, DRF >=3.17.1, drf-spectacular >=0.30.0,
PDM/Ruff, Channels/Daphne, PostgreSQL/Redis em produção. SQLite opcional local.

Entradas atuais: `app/api.py`, `app/urls.py`, `app/asgi.py`, `app/settings/`;
`modules/accounts/`, `modules/organizations/`, `modules/transport/`,
`modules/uploads/`, `shared/`. Worker atual:
`modules/transport/management/commands/process_route_jobs.py`.

Prod atualmente exige `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`,
`DATABASE_URL`, `REDIS_URL`, `PRIVATE_DOCUMENT_ROOT`, `OSRM_URL`, `GEOCODING_URL`,
`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`. Outros nomes estão em
`.env.example` e `app/settings/base.py`; essas exigências ainda não foram adaptadas
à mesma origem. A lista não é o contrato final de deploy.

E-mail de código é síncrono; aprovação atual usa executor após commit (não Celery).
Documentos privados usam storage separado; imagens podem usar Cloudinary. Redis
é necessário para cache/canais entre processos. WhiteNoise e collectstatic já existem,
mas não há montagem/roteamento do build Vue em `app/urls.py`.

## 8. Riscos herdados: não perder durante a substituição dos docs

Esta lista preserva achados da revisão anterior; não equivale a reprodução nova.

| Achado e evidência atual | Encaminhamento |
|---|---|
| `ConfirmPassengerRouteCreateSerializer.create` pode sobrescrever `True` com `False`, ao contrário da action confirm. | Substituir por resposta/pedido/participação com transições explícitas; testar regressão. |
| Senha validada antes do código em `email_token.py`, `user.py` e `email_change.py` de accounts. | Corrigir mantendo tentativas persistidas e antienumeração. |
| Avaliação verifica presença antes do lock, não ao gravar (`driver_rating.py`). | Revalidar participação efetiva na transação; testar concorrência. |
| `LostItemPatchSerializer` admite retorno de estados sem regra de transição. | Fechar transições antes de mudar custódia/reabertura. |
| `DocumentSerializer` inclui `public_id` em resposta autorizada. | Rever minimização; isso não comprova download público. |
| `dispatch_approval_email_on_commit` silencia falha de submissão. | Alinhar aviso de aprovação ao escopo interno e tornar falhas observáveis. |
| Claims de jobs com `skip_locked` não demonstrados em PostgreSQL. | Testes multi-worker com retries e recuperação. |
| Invalidação por signals não cobre `QuerySet.update()`. | Localizar callers e usar invalidação explícita/revisões. |
| Possível N+1 ao pré-criar confirmações e serializar empresas. | Medir; carregar relações/usar serializers próprios quando confirmado. |
| Login/refresh devolvem JWT no corpo além dos cookies. | Consolidar contrato cookie-only da UI, sem tokens no JSON. |
| `Travel` sem agenda concreta, Path compartilhado mutável e PATCH de Path sem proteção equivalente ao optimize. | Modelagem temporal/snapshot; todos os caminhos de escrita via regras comuns. |
| Capacidade pelo total do grupo, e acesso de aluno por grupo em vez de alocação. | Capacidade/REST/WS por participação concreta. |

## 9. Execução, commits e acompanhamento

Commits seguem o padrão predominante do histórico: prefixo convencional e descrição
curta em português (`feat: ...`, `fix: ...`, `chore: ...`; `docs: ...` para documentação).
Realizar **um commit por mudança lógica**, sem agrupar alterações independentes ou
separar artificialmente código/testes/docs da mesma mudança. Consultar `git log`
antes de escolher a mensagem. Nunca incluir trabalho alheio, segredos ou artefatos
gerados indevidos. Não fazer push/merge sem pedido.

Atualizar esta seção e as especificações afetadas no mesmo commit de cada avanço.
Se uma decisão precisar mudar, registrá-la explicitamente; não deixar o documento
descrever como implementado algo que existe apenas como plano.

| Marco | Situação |
|---|---|
| Registro do plano e substituição dos documentos anteriores | Concluído em 2026-11-15. |
| Tutorial de build Vue separado | Registrado em BUILD_VUE.md; integração ainda não implementada. |
| Etapa 0 — especificação técnica detalhada e estratégia de migrations | Decisões de vínculo, pedidos, publicação, viagem única e regeneração registradas. Exceções restantes na seção 3.4. Conjunto de schema da Etapa 1 expressamente autorizado; sem aplicação no banco habitual. |
| Etapa 1 — modelagem | Cobertura estrutural 1.1–1.6 implementada e testada (seção 11), sem declarar substituição integral: callers/campos antigos ainda necessários têm remoção coordenada nas Etapas 2/3. Nenhum novo fluxo operacional ativado. |
| Etapa 2 — regras | Iniciada: serviços isolados de solicitar/aprovar/recusar/retirar vínculo, com auditoria e aviso atômicos. Encerramento/configuração e demais recortes pendentes; ver seção 12. Sem ativação operacional. |
| Etapa 3 — API/admin/integração | Não iniciada. |
| Etapa 4 — ambiente/build/operação | Não iniciada. |

**Validações do registro inicial (2026-11-15, antes da revisão de ambiguidades):** `pdm run test` passou
46/46 com SQLite de teste isolado e integrações externas desabilitadas; `pdm run lint`
passou (118 arquivos). Houve aviso de diretório `staticfiles/` ausente; não há build
Vue implantado. Não executados nesta tarefa: schema, check-deploy, migrations,
serviços persistentes ou testes PostgreSQL/Redis/navegador. Esses resultados não
comprovam implementação nem cobertura do fluxo novo.

Documentação: `git diff --check` passou; links locais e fechamento de blocos de
código conferidos nos cinco documentos mantidos/criados. O tutorial não foi
executado contra o frontend, cujo repositório não foi inspecionado nesta tarefa.

**Revisão de ambiguidades (2026-11-15):** distinguidas decisões aprovadas de
recomendações, explicitadas pendências de produto, receita de revisão assíncrona,
geração determinística, limites entre camadas e marco conjunto 3/4. Ajustados guia
dos agentes e tutorial para cookies/WS, cópia segura e contrato de assets. Somente
documentação; testes de aplicação não repetidos porque código/dependências não
mudaram. `git diff --check`, links locais e blocos de código dos cinco documentos
passaram. O bloco de cópia do tutorial foi extraído e executado com arquivos fictícios
em diretório temporário: cópia inicial correta e segunda execução interrompida sem
sobrescrever o destino. Nenhum build Vue real executado; sem novo baseline funcional.

## 10. Etapa 0 — inventário e preparação da transição

### Autorização global dos recortes restantes da Etapa 1

O dono autorizou serviços/autorizações, empresa/garagem da frota, política/dia com
elegibilidade congelada, resposta/pedido, evolução de Travel/participantes/eventos,
snapshots/paradas/publicações, jobs por revisão/claim, convites e avisos, incluindo
migrations incrementais **apenas em bancos temporários de teste**, admin protegido,
testes/fixtures e ajustes mecânicos dos callers. Sem settings/dependências, descarte
de dados, reescrita de migrations ou aplicação no banco habitual. Operação/API novas
continuam para as Etapas 2/3; legado necessário só sai no marco coordenado dos callers.

Decisões complementares aprovadas: aprovação de pedido dentro da prorrogação;
escolha/alocação anterior preservada até cálculo validado (diferente da recomendação
anterior de transferência imediata); publicação **por viagem**; **sem viagem adicional
por serviço/data nesta versão**; desistência por trecho invalida pedido conflitante;
regeneração **automática somente de futuras datas não publicadas**, preservando decisões,
histórico e cancelamentos. Publicadas só por revisão explícita.

Primeiro recorte deste conjunto: `RecurringService`, `PassengerServiceAuthorization`
e `RecurringServiceStop`; dias da semana por máscara 1..127 (segunda bit 1), sentido
independente, horário-alvo de chegada/partida, vigência e escolhas humanas opcionais
durante configuração. Autorização tem ida habitual única e retornos elegíveis;
services futuros revalidarão grupo/empresa/aptidão, sem alocação automática.
Frota nova pertence à empresa e exige capacidade positiva/conhecida; garagem é ponto
operacional. `Vehicle.route_group` fica opcional **somente para a transição**, com
constraint XOR: propriedade empresarial nova ou grupo legado, nunca ambos. API/admin
legados não escrevem veículos empresariais novos. Migration `router.0008` é incremental,
sem backfill; migrar dados legados inválidos requer estratégia/autorização futura.
Validação deste recorte: 23/23 testes (programação/frota + privacidade), 31,525 s.
Primeira tentativa de makemigrations usou o nome do módulo em vez do label `router`,
sem criar arquivo; corrigida. Lint ajustado antes do commit; schema/check ao fim do conjunto.

Segundo recorte: `ResponsePolicy` sem horários universais fixados por default;
`ServiceDay` único por grupo/data com prazos completos, snapshot/revisão e tombstone
de cancelamento; `ServiceDayEligibility` fixa quem era esperado e serviços/ponto
autorizados. `DailyResponse` é única por elegibilidade: ausência de linha é sem
resposta; linha com ambos os serviços nulos é negativa. Ida/retorno e desistências
são independentes. `DailyChangeRequest` separa decisão e aplicação, preserva proposta
e versão esperada; aprovação exige autor/instante anterior ao fim da janela, e não
modifica a resposta automaticamente. Reservas/cálculo/aplicação serão services da
Etapa 2. Migrations incrementais `router.0009`/`0010` (auditoria terminal); 25/25 testes de transport passaram
(10,372 s); lint conferido antes do commit. Modelos novos somente leitura no admin.

Terceiro recorte: `Travel` datada por atendimento/serviço, agenda, preparação e
revisões, com motorista/veículo pendentes no rascunho; uma viagem por serviço/data.
`TravelParticipation` distingue alocação/desistência/ausência/embarque/desembarque,
tem unicidade efetiva por elegibilidade/trecho e horários coerentes no banco.
`ParticipationEvent` preserva autoria, correção referenciada/motivada e ID idempotente;
`SeatReservation` representa capacidade proposta sem substituir a alocação antiga.
Capacidade total, transições e disputa concorrente continuam responsabilidade dos
services da Etapa 2. `Path` passa a PROTECT para não apagar histórico de viagens.
Migration `router.0011`; testes de transport + privacidade passaram 46/46 (43,001 s).
Callers legados de viagens/confirmações/avaliações/objetos/GPS não recebem viagens
datadas; admin não altera essas viagens. Essas barreiras são adaptação transitória,
não implementação da API nova. A localização legada rejeita viagem datada antes de
acessar motorista pendente. Defaults/nullable novos não dispensam validação de publicação.

**Continuação da Etapa 1:** baseline antes dos próximos models encontrou uma falha
no teste de filtro por data de viagens (114/115 passaram). O teste usava data UTC,
mas o filtro usa America/Sao_Paulo. Corrigido para data local, com relógio fixo em
2026-11-16 01h UTC (ainda dia 15 local), sem mudar comportamento da API. Lint do
baseline passou (123 arquivos). Após corrigir um erro intermediário de posicionamento
dos imports, testes de privacidade passaram 10/10 (26,407 s) e a suíte completa
115/115 (136,356 s); lint passou. Ambiente SQLite temporário
`/tmp/opencode/nextrouter-stage1.sqlite3`, Redis/geocodificação/OSRM/SMTP/Cloudinary
desabilitados por variáveis de shell; nenhum banco habitual alterado.

### 10.1. Escopo e evidências desta execução (2026-11-15)

Primeiro avanço da Etapa 0, sobre o código da revisão `78acfb3`, com árvore de
trabalho inicialmente limpa. **Não é conclusão da Etapa 0 nem implementação do
domínio novo.** Inventário estático e baseline executados nesta sessão; achados de
concorrência abaixo são riscos identificados por leitura, não corridas reproduzidas.
Nenhuma alteração de código, settings, dependências ou migrations neste avanço.
O frontend separado não foi acessado.

### 10.2. Mapa atual → alvo e dependentes

Os caminhos das tabelas são relativos à raiz. Nomes de recursos futuros continuam
conceituais; não constituem um contrato de URLs nem schema aprovado.

| Área e evidência no código atual | Diferença para o alvo e dependentes da transição |
|---|---|
| `modules/organizations/models/passenger.py` e `driver.py`: cada perfil tem uma única FK `route_group` opcional e flags de aprovação/recusa no próprio perfil. | Empresa é inferida do grupo; não existe vínculo empresarial com ciclo de vida próprio. Separar vínculo, participação no grupo e autorização de serviços. Rever serializers, permissões, admin, filtros, otimização e WS que percorrem essa FK. |
| `modules/organizations/api/views/passenger.py` e `driver.py`, ação `request_route_group`: novo pedido substitui o grupo atual e zera aprovação. Serializers de PATCH também resetam aprovação ao mudar grupo. | Pedido a outra empresa não pode sobrescrever o vínculo ativo. Mover grupo na mesma empresa não pode exigir nova aprovação empresarial. Regras de pedidos pendentes/troca dependem da seção 3.4. |
| Views de passageiro/motorista admitem `destroy` pelo próprio usuário ou empresa proprietária do grupo, usando o fluxo padrão do viewset. | Encerrar vínculo deve ser uma ação distinta de apagar perfil/conta. Revisar ações, proteção de histórico e clientes; não assumir que todo DELETE atual será executável, pois FKs podem protegê-lo. |
| `modules/organizations/models/company_route_group.py`: empresa, nome único por empresa, CEP comum e coordenadas de referência. | Falta destino operacional com endereço completo, elegibilidade e política por grupo. Coordenada de referência/CEP não equivale ao destino preciso. |
| `modules/transport/models/company_route_schedule.py`: par obrigatório `go_hour`/`return_hour`, retorno maior que ida, unicidade por grupo/par de horas. | Substituir por serviços independentes, dias da semana, sentido, horário-alvo e escolhas habituais. Afeta API de horários, admin, estatísticas e seeds. |
| `modules/transport/models/vehicle.py`: veículo pertence ao grupo, motorista responsável opcional, garagem só por CEP e capacidade anulável. | Propriedade deve ser da empresa; exigir capacidade conhecida e positiva para operar e ponto preciso da garagem. Ajustar ownership, serializers e start; manutenção não escolhe substituto automaticamente. |
| `modules/transport/models/travel.py`: empresa, motorista obrigatório, veículo opcional, Path compartilhado, status de execução e horários reais. | Faltam data de atendimento, serviço, agenda planejada, revisão/preparação e publicação. `path` usa CASCADE; excluir um trajeto pode alcançar viagens e seus dependentes. Revisar exclusão/histórico antes de remover relações antigas. |
| `modules/transport/api/views/travel.py` e serializer correspondente: criação gera confirmações de todos os alunos aprovados do grupo; criação/start usam total do grupo para capacidade. | Resposta diária deve anteceder viagem publicada; capacidade deve usar alocações concretas. Start/finish/cancel estão na view, não num serviço comum ao admin/worker. |
| `modules/transport/models/confirm_passenger_route.py`, serializers e views: registro por viagem/usuário com booleano `confirm`; POST faz `update_or_create`, action `confirm` só muda para verdadeiro. | Não distingue sem resposta, negativa, pedido, alocação e embarque. Substituir pelos registros separados, sem reinterpretar confirmação antecipada como prova de embarque. POST pode voltar de verdadeiro para falso; manter caso de regressão. |
| `modules/transport/models/path.py`, `optimization.py` e API de paths: geometria e paradas mutáveis por grupo, sem snapshot de viagem/revisão. | Separar configuração habitual e resultado concreto versionado. `optimize` bloqueia viagem ativa, mas PATCH/admin não passam pela mesma regra de operação. Start não exige percurso pronto/atual/publicado. |
| `modules/transport/services.py`: localização transacional e broadcast pós-commit; também helpers de trajeto automático/geocodificação. | Reaproveitar validação de localização e pós-commit; converter o arquivo em pacote somente junto com todos os imports afetados. Helpers existentes não provam que sincronização automática seja o novo fluxo aprovado. |
| `modules/transport/signals.py`: alterações/remoção de passageiro e endereço do usuário invalidam Path; `Path.save` invalida por mudança de pontos/grupo. | Alterar endereço pessoal ainda afeta planejamento; não existe ponto operacional independente. Adotar invalidação explícita por revisão. Escritas em massa não têm a mesma cobertura dos hooks. |
| `modules/transport/models/route_optimization_job.py`, `optimization.py`, management command `process_route_jobs.py`: job por Path, IDs de passageiros, origem/fim, tentativas e timeout. | Não há jobs de geração/fechamento, revisão de viagem ou identificador de claim. As coordenadas dos passageiros são lidas do perfil no processamento, não congeladas na solicitação. Último ID de job por Path não substitui revisão + claim. |
| `modules/organizations/mixins/is_approved.py`: aprovação transacional na API; e-mail via executor após commit e deduplicação temporária em cache por perfil/grupo. | Substituir aviso operacional por persistência interna atômica com a decisão; não remover e-mail de autenticação. Não existe entidade de aviso/lido. Falha na submissão ao executor é silenciada. |
| `modules/transport/api/serializers/driver_rating.py`: exige viagem finalizada e `confirm=True`; participação é validada antes do lock, não revalidada no create. | Rever elegibilidade por evento operacional efetivo e histórico, na mesma transação. Não concluir que confirmação atual prova viagem realizada. |
| `modules/transport/api/serializers/lost_item.py`: relato exige viagem encerrada e confirmação ou motorista aprovado; PATCH controla papel, mas não uma tabela completa de transições. | Definir custódia/reabertura e acesso histórico antes de substituir as regras. Admin e API precisam compartilhar a mesma transição. |
| `modules/organizations/api/views/company.py`, ação `stats`: hoje usa `started_at` ou qualquer viagem agendada; presenças são cruzadas com os horários do grupo. | Estatísticas novas devem usar data/serviço concretos; todas as agendadas atuais não equivalem a atendimentos de hoje. |

**Ausências confirmadas no inventário de models/rotas:** não há entidades próprias
para vínculo empresarial histórico, serviço semanal independente, política/janela,
atendimento por data, resposta diária por grupo/data, pedido de alteração, participação
com eventos reais, convite de substituição ou aviso persistente. Os conceitos da
seção 4.2 não podem ser tratados como enums já existentes.

### 10.3. Entradas de escrita, acesso e integração

| Superfície | Evidência e trabalho necessário |
|---|---|
| API e contrato | `app/api.py` agrega routers de accounts/organizations/transport e uploads. `modules/organizations/urls.py` e `modules/transport/urls.py` registram os recursos legados; a geração OpenAPI atual é baseline, não contrato do domínio novo. |
| Vínculos e configuração | `/api/passengers/` e `/api/drivers/`, `request-route-group`, `approve`, `reject` precisam separar identidade e vínculo. `/api/company-route-groups/`, `/api/route-schedules/` e `/api/vehicles/` precisam de participação/autorização, serviço independente e propriedade empresarial. Os nomes finais serão fechados com a modelagem. |
| Operação | `/api/confirmations/` será substituído por resposta/pedido/participação; `/api/travels/` e suas ações precisarão de data/revisão/publicação/eventos. `/api/paths/` e `optimize`/`optimization` precisarão distinguir configuração habitual e cálculo por revisão de viagem. |
| Dependentes | `/api/companies/me/stats/`, `/api/driver-ratings/` e `/api/lost-items/` precisam usar atendimento/participação efetiva. Preservar funcionalidades até tratar seus callers; não manter duas escritas autoritativas para o mesmo conceito. |
| Querysets/permissões | `modules/organizations/permissions.py` infere ownership pelo grupo. Views de viagens e consumers liberam aluno aprovado no grupo, sem alocação concreta. Há branches de listagem/leitura ampla para staff; revisar separadamente leitura e escrita, sem transformar isso em bypass de domínio. |
| Admin | `modules/organizations/admin.py` tem review de empresa por `queryset.update` e escrita de perfil com lógica própria de e-mail. `modules/transport/admin.py` permite editar status/relacionamentos/horários de viagem e dados operacionais sem chamar as ações da API. A extração de services deve cobrir formulários e ações, não só serializers. |
| HTTP/cookies | `modules/accounts/api/views/auth.py` já fornece bootstrap CSRF, login/refresh/logout com CSRF, cookies HttpOnly e sessões revogáveis. Ainda retorna access/refresh no JSON; produção usa SameSite=None. `authenticate.py` também aceita Bearer, que evita a ramificação CSRF por cookie. Contrato cookie-only da UI ainda não implementado. |
| Códigos/senhas | `api/serializers/email_token.py` e `user.py` validam força da senha antes do código; `api/views/email_change.py` verifica senha atual antes de `check_email_token`. Corrigir posteriormente com regressão de tentativas persistidas/antienumeração. |
| WebSocket | `app/asgi.py` usa `OriginValidator` com `CORS_ALLOWED_ORIGINS`. `modules/accounts/ws_auth.py` aceita cookie e fallback Bearer; `modules/transport/consumers.py` usa grupo e revalida sessão/expiração nas mensagens. Acesso inicial a posição exige viagem ativa; há fechamento após finish. Migrar acesso para participação/designação e separar allowlist WS de CORS. Não houve teste WS nesta execução. |
| Uploads/downloads | `modules/uploads/api/views.py` permite upload público pré-cadastro, sem listagem; download de documento exige titular ou admin. `models/document.py` usa storage privado em `PRIVATE_DOCUMENT_ROOT`, fora da mídia pública. Preservar isso ao mudar vínculos e minimizar os dados serializados. |
| SPA/estáticos | `app/urls.py` só registra admin/API e mídia em DEBUG; nenhum build/fallback Vue. WhiteNoise e coleta já existem em settings. Seguir `BUILD_VUE.md` como proposta de artefato, não comportamento implementado. |

### 10.4. Jobs, fixtures e clientes que não podem ficar esquecidos

- `process_route_jobs.py` executa apenas otimização. Mantê-lo como ponto de partida
  do worker por management command; não há agendamento semanal/fechamento hoje.
- `claim_job` usa timeout de cinco minutos e três tentativas; `_retry` grava por
  ID/status, sem token da tentativa. São valores **atuais**, não escolhas aprovadas
  para o novo worker. Um processamento antigo não é isolado de um claim recuperado;
  testar e corrigir esse risco ao implementar revisão/titularidade, sem alegar
  comprovação de concorrência com o baseline SQLite.
- `modules/transport/management/commands/seed_data.py`, `seed_demo_data.py` e
  `backfill_user_data.py` dependem do domínio legado. Adaptar por marco, sem executar
  seeds/backfill em dados reais ou acoplá-los ao startup.
- `tests/helpers.py` cria grupos por CEP e passageiros por `route_group`; importa
  utilitários dos seeds/backfill. Atualizá-lo junto das primeiras mudanças de schema,
  incluindo fixtures de empresa/vínculo/grupo separados.
- A suíte atual cobre autenticação/códigos, cadastro, review, privacidade/downloads,
  isolamento de alguns filtros e schema. `modules/transport/tests/__init__.py` está
  vazio: não há uma suíte própria de geração, prazos, publicação, embarque, OSRM ou
  concorrência do novo domínio. Existem testes de privacidade com viagens em
  `modules/organizations/tests/test_privacy.py`; não confundir a ausência de testes
  próprios de transport com ausência absoluta de testes que usam Travel.
- `html-template-test/` contém clientes locais para contas, empresas, vínculos,
  grupos/horários, veículos, trajetos/OSRM, viagens/presença, localização WS e
  objetos/avaliações. `COBERTURA.md` descreve o contrato legado, mas não substitui
  o código: por exemplo, lista status `inactive` de veículo, ausente nas choices
  atuais (`active`, `maintenance`). Conferir cada cliente ao trocar o contrato.
  Não publicar essa pasta nem usar seu catálogo como especificação do alvo.

### 10.5. Migrations: inventário, sem autorização de mudança

No inventário da revisão `78acfb3`, havia 8 migrations de accounts, 3 de
organizations, 7 de transport e 3 de uploads. As adições `organizations.0004` e
`0005`, criadas posteriormente com autorização, estão nas seções 10.9/10.10.
Labels continuam `authenticator`, `organizations`, `router` e `uploader`; nomes de
tabelas conservam prefixos antigos. Pontos críticos do histórico:

- `modules/accounts/migrations/0001_initial.py` cria também os perfis/empresa/grupo
  antigos; `0003_driverrating.py` cria a avaliação antiga.
- `modules/organizations/migrations/0001_initial.py` transfere estado dos modelos
  por `SeparateDatabaseAndState`, sem recriar suas tabelas. Depende de
  `authenticator.0005_usersession` e `uploader.0003`.
- `modules/transport/migrations/0005_modular_boundaries.py` altera estado de FKs e
  assume DriverRating, também sem recriar tabelas. Depende de `organizations.0001`.
- `modules/accounts/migrations/0006_modular_boundaries.py` remove esses modelos
  apenas do estado de accounts e move ContentTypes preservando IDs. Depende de
  `router.0005`; as branches não podem ser descartadas isoladamente.
- As folhas locais são accounts `0008`, organizations `0003`, transport `0007` e
  uploads `0003`. O baseline de testes conseguiu construir seu banco temporário;
  isso não informa quais migrations estão aplicadas em bancos de desenvolvimento.

**Proposta no inventário inicial:** conservar o histórico e adicionar migrations
incrementais por subetapa; validar instalação desde zero em banco novo isolado.
Posteriormente autorizada para 10.9/10.10 e, na continuação, para o conjunto restante
da Etapa 1 descrito na abertura da seção 10. Não é necessário
reescrever migrations antigas apenas porque dados demo são dispensáveis. Fechar
o recorte de ER/transição antes de solicitar autorização concreta para cada novo
conjunto. Não consultar nem descartar o banco habitual para este inventário.

### 10.6. Baseline desta execução e limites

Comandos executados da raiz com variáveis de shell sobrescrevendo eventual `.env`:

```sh
export DATABASE_URL=sqlite:////tmp/opencode/nextrouter-etapa0.sqlite3
export REDIS_URL=
export GEOCODING_URL=
export OSRM_URL=
export EMAIL_HOST=
export CLOUDINARY_URL=
export PRIVATE_DOCUMENT_ROOT=/tmp/opencode/nextrouter-etapa0-documents
pdm run test
pdm run lint
pdm run check
pdm run schema
```

- `test`: **46/46 passaram**, 115,705 s na execução completa. A primeira tentativa
  foi interrompida pelo limite de 120 s após 43 pontos de progresso e não conta
  como sucesso; a repetição com limite de 300 s concluiu. Django criou/destruiu o
  banco de teste; nenhum `migrate` foi executado sobre o banco habitual.
- `lint`: passou; 115 arquivos já formatados. O número desta execução difere do
  registro inicial; não usar a contagem antiga como resultado novo.
- `check`: sem problemas de sistema e sem mudanças de models detectadas pelo
  `makemigrations --check --dry-run`. Nenhuma migration criada/aplicada manualmente.
- `schema`: passou, com validação e `--fail-on-warn`; artefato somente em
  `/tmp/opencode/nextrouter-schema.yaml`, fora do commit.
- Aviso durante os testes: diretório `staticfiles/` ausente. Não foi criado um
  build Vue nem executado collectstatic para ocultar esse aviso.
- Documentação: `git diff --check`, links locais, fechamento dos blocos de código
  e contagem dos arquivos de migrations conferidos, sem problemas. Após esta
  mudança exclusivamente documental, não foi repetida a suíte funcional.
- Não executados: PostgreSQL, Redis, worker persistente, navegador/Vue, chamadas
  reais a geocodificação/OSRM/SMTP, check-deploy ou deploy. Baseline não comprova
  locks, recuperação multiprocesso, WS nem o novo fluxo aprovado.

### 10.7. Próximo recorte da Etapa 0

1. Recorte de vínculo respondido pelo dono: grupo único, um ciclo pendente/ativo,
   retirada pelo titular, encerramento por titular/empresa e bloqueio em operação
   ativa. Regras registradas na seção 10.8; estrutura parcial implementada em 10.9.
2. Participação em grupo e pontos têm estrutura parcial na seção 10.10. Antes de
   ativar o novo caminho, detalhar serviços/autorização e fechar regras de regeneração
   de dias gerados, preservação de respostas/alocações e efeitos em viagens futuras.
   Implementar bloqueio de encerramento com participação real, não o booleano legado.
3. Continuar ER e tabelas dos demais eixos conforme suas decisões bloqueantes
   (seção 3.4), contrato de integração e mapa final de endpoints. Não fixar enums
   completos, unicidade de viagem/serviço ou regras de encerramento antes disso.
4. Os conjuntos 10.9/10.10 e o restante da modelagem da Etapa 1 foram autorizados
   expressamente. Isso não autoriza settings/dependências, backfill, descarte de dados
   ou aplicação no banco habitual. Demais conjuntos exigem novo escopo concreto.

### 10.8. Primeiro recorte de organizações: decisões e especificação preliminar

**Decisões aprovadas pelo dono nesta execução (2026-11-15):**

- À pergunta sobre vários grupos ativos por aluno na mesma empresa, respondeu
  **“Um grupo”**. A participação ativa do aluno terá cardinalidade máxima de um
  grupo na empresa; pode existir vínculo aprovado ainda sem grupo designado.
  Isso não restringe o motorista a um grupo nem reduz as opções de retorno
  autorizadas do aluno dentro do grupo.
- À pergunta sobre solicitar outra empresa com vínculo ativo, respondeu
  **“Só após encerrar”**. Vale para aluno e motorista. Solicitar outra empresa
  deve falhar enquanto existir vínculo ativo; não trocar empresa nem zerar sua
  aprovação. Os detalhes complementares foram respondidos na continuação abaixo.
- Na continuação, confirmou **um pedido pendente por perfil** quando não há vínculo
  ativo; **retirada pelo titular** antes da decisão; **encerramento pelo titular ou
  empresa**, sem apagar identidade/histórico; e **bloqueio do encerramento** quando
  há participação operacional em viagem em andamento.
- Para esse bloqueio, a pergunta definiu participação operacional como motorista
  designado ou aluno alocado ainda sem desistência/ausência/desembarque. A regra
  será aplicada pelo serviço com a modelagem concreta de participação; `confirm`
  do legado não comprova esses estados. Não foi aprovado encerramento agendado.

**Orientação técnica preliminar:** separar o ciclo do vínculo da configuração de
grupo; nomes/campos abaixo ainda serão revisados antes do schema. Não criar uma
coluna `company` e conservar as flags/grupo atuais como uma segunda fonte de verdade.

#### Catálogo parcial de entidades, ownership e integridade

| Entidade conceitual | Campos/relações propostos e nulabilidade | Integridade, ciclo e exclusão |
|---|---|---|
| Perfil Passageiro/Motorista existente | Identidade do usuário obrigatória; CNH opcional no motorista, como hoje. | Não pertence à empresa. Aprovação empresarial e grupo saem do perfil no marco que tratar todos os dependentes. Novas relações de usuário usam `settings.AUTH_USER_MODEL`; não alterar label da identidade incidentalmente. |
| Vínculo empresarial (tentativa/ciclo) | Empresa obrigatória; exatamente um perfil proprietário (passageiro **ou** motorista); estado, solicitante e criação obrigatórios; decisão/revisor, retirada/autor e encerramento/autor opcionais enquanto o evento não ocorreu. | Estrutura implementada em `CompanyMembership` (10.9). Unicidade condicional de um ciclo **pendente ou ativo** por perfil, não uma unicidade independente para cada estado. Checks de proprietário exclusivo e coerência estado/timestamps; aprovação, ownership e impedimento de novo pedido exigem serviço transacional. FKs históricas protegidas contra cascata; retenção continua pendente. |
| Evento de vínculo | Vínculo obrigatório; ação, autor e instante obrigatórios; motivo opcional, limitado a 500 caracteres. | Estrutura implementada em `MembershipEvent` (10.9), com uma ação de cada tipo por ciclo para deduplicação. Trilho append-only será garantido nos services e superfícies expostas, não por triggers ou por sobrescrever save. Aviso persistente será gravado na mesma transação quando essa entidade estiver disponível. Payload não replica CPF, endereço ou documentos. Exclusão/anonimização administrativa depende de retenção, não de DELETE empresarial. |
| Participação do aluno no grupo | `PassengerGroupMembership`, implementado em 10.10: vínculo e grupo obrigatórios, ponto habitual opcional durante configuração, início/autor e fim/autor. | No máximo uma participação aberta por vínculo no banco. Validação local rejeita motorista, falta de aprovação, grupo/ponto de outra empresa e participação fora do ciclo empresarial. Serviço deverá revalidar sob lock; não usar essa relação para o motorista nem presumir que constraints entre tabelas existem. |
| Ponto operacional/autorização de serviço | `OperationalPoint` em 10.10; `RecurringService`/`PassengerServiceAuthorization` e snapshots acrescentados na continuação (seção 11). Destino opcional no grupo durante transição. | Não copia alterações posteriores do perfil nem faz cálculo em save. FK para ponto não é snapshot: dados concretos são congelados em RouteSnapshot/RouteStop. Regeneração automática de futuras datas não publicadas aprovada; conflitos/granularidade ainda na seção 3.4. |

Essa decomposição preserva uma identidade por usuário e histórico por ciclo de
vínculo. A tabela compartilhada `CompanyMembership` usa uma relação explícita com
cada tipo de perfil e check de exclusividade, evitando referência genérica sem
integridade referencial. Essa escolha técnica foi implementada no marco autorizado.
Não impor unicidade apenas `(perfil, empresa)` sobre todo o histórico, pois isso
impediria representar outro ciclo sem sobrescrever uma decisão anterior.

#### Transições do vínculo: o que já é conhecido e o que falta fechar

Estados representados no modelo do marco 10.9: `pending`, `active`, `rejected`,
`withdrawn` e `ended`. Ainda não há serviço que execute essas transições no domínio
novo. Empresa não aprovada é uma condição de aptidão independente: não transformar
automaticamente vínculo ativo em encerrado nem definir acesso em viagem por acidente.

| Operação | Origem → destino conceitual | Regra conhecida / limite pendente |
|---|---|---|
| Solicitar empresa | Sem ciclo pendente/ativo → novo registro pendente | Titular solicita empresa aprovada; vínculo ativo ou outro pedido pendente bloqueia nova solicitação. Repetição da mesma operação retorna seu resultado sem criar outro ciclo. Não modificar tentativa terminal para apagar seu histórico. |
| Aprovar pedido | Pendente → ativo | Empresa aprovada dona do pedido decide. Revalidar ciclo/ownership sob lock; aprovação não exige que o grupo já esteja designado e não publica viagens. Pedido retirado, recusado ou encerrado não pode ser aprovado. |
| Recusar pedido | Pendente → recusado | Empresa dona decide; preservar identidade, decisão e autoria. Recusa de um pedido não encerra automaticamente outro vínculo nem pode ser usada como desativação genérica de vínculo ativo. |
| Repetir mesma decisão | Mesmo estado e mesma operação | Proposta técnica de idempotência: retornar decisão sem duplicar evento/aviso. Uma decisão oposta sobre pedido já decidido é conflito, não PATCH de estado. |
| Encerrar vínculo | Ativo → encerrado | Titular ou empresa encerra sem apagar conta/histórico; rejeitar durante participação operacional em andamento conforme definição acima. Encerramento não é aprovação automática da próxima empresa. Efeitos nas viagens futuras precisam do recorte de vigência. |
| Retirar pedido | Pendente → retirado | Somente titular retira pedido ainda pendente; a empresa não pode aprová-lo depois. Preservar autoria/instante. Nova solicitação depois de retirada cria outro ciclo. |
| Trocar grupo interno | Vínculo continua ativo; participação antiga termina e nova começa | Empresa mantém a aprovação empresarial e limita o aluno a um grupo ativo. Serviço transacional encerra/inclui participações sem dois grupos vigentes. Vigência sobre atendimentos já gerados e execução ativa permanece pendente. |

#### Fronteira transacional e testes previstos para esse recorte

- Proposta local de lock: bloquear primeiro o perfil estável, depois vínculos por
  ID e participações por ID. Solicitação e aprovação do mesmo perfil precisam
  disputar o mesmo lock; bloquear apenas pedidos diferentes não serializa a
  ausência de vínculo ativo. A ordem global com viagens/jobs será definida antes
  de integrar esse recorte à operação.
- Constraints defendem unicidade/estrutura; serviço reobtém os dados, valida ator,
  aprovação da empresa e ownership. API e admin não aceitam alteração direta de
  estado, perfil proprietário ou empresa para contornar uma transição.
- Testar: aluno/motorista ativo não solicita outra empresa; tentativa conserva
  aprovação/empresa/grupo; aprovar sem grupo é possível; grupo de outra empresa é
  rejeitado; segundo grupo ativo é rejeitado; troca interna preserva aprovação;
  histórico do vínculo e viagens não muda ao criar um novo ciclo.
- Testar duas aprovações concorrentes para o mesmo perfil e duas atribuições de
  grupo com conexões distintas em PostgreSQL. Não considerar duas chamadas
  sequenciais ou SQLite como evidência de exclusão mútua.
- A autorização inicial deste catálogo era apenas documental. A continuação
  autorizou expressamente o primeiro marco estrutural da seção 10.9; não usar
  essa autorização para implementar outros eixos ou declarar a Etapa 1 concluída.

**Validação deste segundo avanço:** somente documentação; `git diff --check`, links
locais e blocos de código conferidos. Sem repetição de testes funcionais após as
decisões, pois nenhum código/settings/dependência mudou. O baseline da seção 10.6
foi executado nesta sessão, antes desses dois avanços documentais.

### 10.9. Marco estrutural 1.1a — vínculo e auditoria, sem ativação operacional

**Autorização expressa do dono nesta continuação (2026-11-15):** criar
`CompanyMembership` e `MembershipEvent`, gerar migration incremental e aplicá-la
somente nos bancos temporários de teste; incluir constraints/testes e admin somente
de leitura. Sem alterar settings/dependências, reescrever migrations, copiar/apagar
dados ou aplicar no banco habitual. A autorização não abrange os próximos schemas.

**Implementado neste marco:**

- `modules/organizations/models/company_membership.py`: empresa e um único perfil
  (passageiro ou motorista), estados, solicitante, revisão, retirada, encerramento
  e seus horários/autores. Todas as novas FKs de usuário usam `settings.AUTH_USER_MODEL`.
- Constraints de banco: exatamente um perfil; no máximo um ciclo `pending` **ou**
  `active` por perfil, inclusive entre empresas distintas; estados válidos e
  coerência de status com pares autor/horário; revisão/retirada não anteriores à
  solicitação e encerramento não anterior à revisão. Igualdade temporal é aceita.
  Ciclos terminais preservados não impedem outra solicitação, inclusive à mesma empresa.
- `modules/organizations/models/membership_event.py`: evento com autor, instante,
  ação e motivo opcional. Ações válidas e uma ocorrência por `(vínculo, ação)`;
  cada novo ciclo tem seus próprios eventos. Não há PII replicada automaticamente.
- FKs com PROTECT preservam empresa/perfil/atores referenciados; eventos impedem
  exclusão acidental do ciclo. Isso não define retenção ilimitada: descarte ou
  anonimização controlados continuam dependentes da política ainda pendente.
- `modules/organizations/migrations/0004_company_memberships.py`: apenas cria
  essas tabelas/constraints. Não altera os modelos/tabelas antigos, não faz backfill
  e não reescreve o histórico de migrations. A nova folha de organizations é `0004`.
- `modules/organizations/admin.py`: ambos os novos modelos só para consulta por
  staff com permissão de leitura. Add/change/delete e ações em massa desabilitados,
  inclusive para superusuário; empresa comum não recebe acesso ao admin.
- Testes em `test_membership_models.py` e `test_membership_admin.py` de organizations:
  estados/horários, unicidade entre empresas/perfis, histórico, autoria, FKs protegidas,
  `full_clean`, negações de `create`/`bulk_create`/`update` e admin por HTTP.

**Coexistência transitória e marco de remoção — obrigatório:**

- Único caminho **operacional** continua sendo a API/admin/worker legados, que usam
  `route_group`, `is_approved` e `is_rejected` dos perfis. Não há endpoint novo,
  escrita de produção nos modelos novos, sincronização automática ou espelhamento.
  As tabelas novas são estrutura ainda não ativada; não servem para autorizar REST/WS.
- Teste de regressão comprova que criar estrutura nova em banco de teste não muda
  flags/grupo do legado e não fabrica eventos. Constraints não são máquina de
  transições: não validam ator, empresa aprovada, correspondência do autor ao
  perfil, estado anterior, coerência evento/vínculo ou participação em viagem ativa.
  Essas regras exigem o serviço autorizado e transacional, ainda não implementado.
- A substituição operacional ocorrerá num marco coordenado de services/callers:
  API, admin, permissions, filtros, viagens, otimização, WS, estatísticas, seeds,
  helpers e clientes manuais. Nesse marco, remover flags/grupo antigos como fonte
  de vínculo; não habilitar um endpoint novo deixando caminhos antigos escreverem
  uma interpretação concorrente. Remoção de schema/backfill requer nova autorização.
- Neste marco 1.1a, participação histórica em grupo/ponto/serviços não foi criada;
  a estrutura de grupo/ponto foi acrescentada depois em 10.10, ainda sem serviços.
  Também não foram implementados avisos persistentes, encerramento/retirada operacionais, snapshots,
  mudanças em viagens futuras ou a regra real de bloqueio durante viagem ativa.
  Por isso a subetapa 1.1, a Etapa 0 e o novo fluxo funcional **não estão concluídos**.

**Validações desta continuação:** baseline antes do código: 46/46 testes em
115,316 s e lint (115 arquivos) passaram, com serviços externos desabilitados.
Após a implementação, 28/28 testes específicos passaram em 9,907 s. Houve uma
negação inicial de lint por linha longa no teste, corrigida. Validação completa:

- `pdm run test`: **74/74 passaram**, 132,310 s; banco de teste construído desde
  zero com a migration nova e destruído pelo runner. Sem aplicação no banco habitual.
- `pdm run lint`: passou; 119 arquivos já formatados.
- `pdm run check`: sem problemas de sistema, sem mudanças de models pendentes.
- `pdm run schema`: passou com validação/`--fail-on-warn`, sem expor recursos novos;
  artefato somente em `/tmp/opencode/nextrouter-schema.yaml`.
- Shell forçou `DATABASE_URL=sqlite:////tmp/opencode/nextrouter-memberships.sqlite3`,
  `REDIS_URL=`, `GEOCODING_URL=`, `OSRM_URL=`, `EMAIL_HOST=`, `CLOUDINARY_URL=` e,
  nos testes, `PRIVATE_DOCUMENT_ROOT=/tmp/opencode/nextrouter-membership-documents`.
- Documentação e diff: links locais, blocos de código e `git diff --check` conferidos.
  Referências consultadas: documentação oficial Django 6.0 de constraints e
  permissões/ações de ModelAdmin via Context7.
- Continua o aviso de `staticfiles/` ausente. Não executados PostgreSQL, Redis,
  navegador/Vue, worker persistente, serviços externos reais, check-deploy ou deploy.
  Os testes de constraints SQLite **não comprovam locks nem corridas concorrentes**.

### 10.10. Marco estrutural 1.2a — grupos e pontos, sem ativação operacional

**Decisão de produto nesta continuação (2026-11-15):** à pergunta sobre alterações
de grupo, ponto habitual, serviços ou política em atendimentos futuros já gerados,
o dono respondeu **“Gerar novamente e aplicar as mudanças.”** Não escolheu entre
atualização automática ou ação explícita nem delimitou dias não publicados versus
publicados. Registrar a intenção de reaplicação por regeneração; fechar os limites
antes de implementar o gerador. Isso não autoriza zerar respostas/pedidos/alocações,
recriar cancelados ou reescrever viagens passadas/em andamento. Publicação continua
exigindo revisão atual pronta, decisão da empresa e aviso quando revisada.

**Complemento posterior:** na autorização global da Etapa 1, escolheu regeneração
automática somente de futuras datas não publicadas. Esse complemento substitui a
pendência geral acima; conflitos e dia parcialmente publicado ainda precisam ser fechados.

**Autorização expressa:** criar `OperationalPoint` e `PassengerGroupMembership`,
adicionar `destination` opcional ao grupo, incluir constraints/validações locais,
testes e admin somente de leitura para os novos modelos; gerar migration incremental
e aplicá-la apenas em bancos temporários de teste. Sem endpoints novos, alteração
de settings/dependências, backfill, descarte de dados ou aplicação no banco habitual.

**Implementado neste conjunto:**

- `modules/organizations/models/operational_point.py`: ponto da empresa, com nome,
  logradouro, número, complemento opcional, bairro, cidade, UF, CEP, coordenadas,
  autor e criação. Não tem FK para o endereço pessoal, mixin de geocodificação,
  chamada HTTP, signals de sincronização ou geração de Path em save.
- Banco exige coordenadas não nulas e dentro dos limites geográficos; nome/campos
  obrigatórios de endereço não podem ser strings vazias. `clean` também rejeita
  campos só com espaços, coordenadas inválidas/não finitas. Isso não comprova que
  o endereço exista, que CEP/UF estejam corretos ou que o ponto seja seguro para parar.
- `modules/organizations/models/passenger_group_membership.py`: referência ao ciclo
  empresarial, grupo e ponto habitual opcional enquanto a configuração estiver
  incompleta; início/autor e fim/autor. Não é participação/embarque de viagem.
- Constraints: uma participação aberta (`ended_at IS NULL`) por vínculo; fim exige
  autor e vice-versa; fim não pode anteceder início. Ciclos encerrados preservam
  histórico e permitem nova participação, inclusive no mesmo grupo. Não existe
  unicidade do ponto: vários alunos podem compartilhar a mesma parada física.
- Validação local via `clean`/`full_clean`: vínculo precisa ser de passageiro e
  possuir aprovação (ativo, ou encerrado apenas para histórico fechado); grupo,
  vínculo e ponto devem ser da mesma empresa; início não pode anteceder aprovação
  empresarial e fim não pode ultrapassar encerramento do vínculo. Instantes sem
  fuso e IDs inválidos são tratados como erro de validação, não falha de comparação
  ou de acesso à relação. Nenhum desses checks entre tabelas substitui lock no serviço.
- `CompanyRouteGroup.destination`: FK opcional para ponto, com exclusão protegida.
  `clean` valida mesma empresa. Continua opcional **para preservar a transição**;
  operação nova ainda deverá exigir destino completo. `common_cep` e coordenadas
  de referência legados não foram removidos, reinterpretados ou sincronizados.
- `modules/organizations/migrations/0005_operational_points_and_group_memberships.py`:
  cria as duas tabelas/constraints e adiciona FK anulável, sem backfill nem destruição
  de tabelas/colunas. Depende da `organizations.0004` e do usuário configurado.
- Admin: `OrganizationStructureReadOnlyAdmin` compartilhado por todos os modelos
  novos; novos pontos/participações também negam add/change/delete e ações em massa,
  inclusive ao superusuário. Listagem de pontos não inclui endereço/coordenadas;
  consulta individual permanece restrita a staff autorizado. O admin legado do grupo
  não expõe `destination` para escrita nem recebeu uma ação de configuração paralela.
- Fixtures fictícias: helper `tests/helpers.py:create_operational_point`; novos testes
  em `test_operational_points.py` e `test_passenger_group_membership.py`, além dos
  testes HTTP de admin ampliados para os quatro modelos estruturais.

**Limites e coexistência — não declarar entrega operacional:**

- API/admin/worker antigos continuam o único caminho operacional, conforme 10.9.
  Nenhum novo endpoint ou serialização de ponto/endereço foi acrescentado. Teste
  verifica que a API legada não expõe nem escreve `destination`; seu comportamento
  atual de ignorar campo fora do serializer não é o contrato-alvo de uma nova API.
- `save` não chama `full_clean`. ORM direto/bulk/update não garantem mesma empresa,
  papel, aprovação, cronologia entre tabelas, autoria autorizada ou encerramento
  coordenado de grupos ao encerrar o vínculo. As constraints são defesa estrutural;
  o futuro serviço deverá revalidar tudo na transação, inclusive sob concorrência.
- A unicidade de uma participação aberta é **por vínculo**, não uma constraint
  SQL arbitrária entre perfil/estado empresarial/grupo. Proibir grupo aberto em
  ciclo encerrado é validação local e deverá ser invariante transacional do serviço.
  Também não foi implementada agenda de mudanças futuras nem exclusão de sobreposição
  de todos os intervalos históricos; não prometer isso com essa unicidade parcial.
- FK de participação para ponto não congela o conteúdo do endereço. Snapshots de
  atendimento/viagem, revisão de pontos, serviços habituais/autorizados e regeneração
  continuam fora deste conjunto. Alterar perfil pessoal não muda o ponto, mas isso
  não autoriza alterar silenciosamente um ponto já usado por viagem publicada.
- Ponto nulo representa configuração incompleta, não autorização para operar sem
  local de transporte. Ainda falta o serviço que valide prontidão operacional.
- FKs protegidas preservam referências; política de retenção/anonimização continua
  pendente. Grupo único não significa limitar serviços/retornos nem grupos do motorista.
- A Etapa 0 e as subetapas 1.1/1.2 continuam parciais. Próximo recorte: detalhar
  serviços independentes, autorizações e propriedade da frota; fechar as decisões
  bloqueantes antes de definir suas unicidades e criar outro conjunto de migrations.

**Validações desta continuação:** baseline antes do código: **74/74** testes em
124,648 s e lint (119 arquivos) passaram. Depois, **44/44** testes específicos
(incluindo admin ampliado) passaram em 15,230 s; suíte completa **113/113** passou
em 135,346 s. Após ajustar a ordem dos métodos e acrescentar duas regressões de
admin (permissão somente de leitura para staff e destino não editável no formulário
legado), validação final: **115/115** testes em 136,757 s; lint passou (123 arquivos),
check sem problemas ou alterações de models pendentes, schema validado sem novos
recursos de API. A primeira checagem de formatação apontou dois testes para ajuste;
o primeiro lint da suíte completa apontou a ordem de métodos de dois models, corrigida.

Ambiente forçado: `DATABASE_URL=sqlite:////tmp/opencode/nextrouter-group-points.sqlite3`,
`REDIS_URL=`, `GEOCODING_URL=`, `OSRM_URL=`, `EMAIL_HOST=`, `CLOUDINARY_URL=` e,
nos testes, `PRIVATE_DOCUMENT_ROOT=/tmp/opencode/nextrouter-group-point-documents`.
Runner criou/destruiu banco temporário com a migration nova. Nenhuma aplicação no
banco habitual; sem PostgreSQL, Redis, navegador, worker persistente, serviços externos
reais, check-deploy ou deploy. SQLite não comprova locks. Continua o aviso de
`staticfiles/` ausente. Referência consultada: documentação Django 6.0 de validação
de instâncias via Context7. Links, blocos de código e `git diff --check` conferidos.

## 11. Cobertura estrutural da Etapa 1 — conjunto autorizado

Esta continuação percorreu todas as subetapas de **modelagem**, com migrations
incrementais, testes de model/negações e barreiras nos callers legados. Não equivale
a implementar os services transacionais, geração, worker novo, API ou WS novos.

| Subetapa | Estrutura presente e validação | Transição/limite real |
|---|---|---|
| 1.1 — vínculo empresarial | CompanyMembership/MembershipEvent; perfil exclusivo, um ciclo pendente/ativo por perfil, autoria/horários, histórico protegido. | Perfil/grupo/flags legados só saem junto de seus callers nas Etapas 2/3. Encerramento real e bloqueio por embarque ainda sem serviço. |
| 1.2 — configuração habitual | OperationalPoint, PassengerGroupMembership, RecurringService, PassengerServiceAuthorization, RecurringServiceStop; sentidos/semana/vigência, ida habitual única, pontos e frota por empresa. | Vehicle aceita **ou** propriedade empresarial nova **ou** grupo legado (XOR); nunca ambos. Veículo novo exige capacidade conhecida/positiva. Destination/ponto/designações podem ficar pendentes durante configuração, não ao operar. |
| 1.3 — política/dia | ResponsePolicy, ServiceDay, ServiceDayEligibility; prazos completos congelados, grupo/data únicos, cancelamento com autoria/motivo e elegibilidade histórica. | Sem rotina de geração/regeneração, calendário externo, valores universais de horário ou exclusão automática de decisões conflitantes. |
| 1.4 — demanda/pedidos | DailyResponse e DailyChangeRequest; ausência de linha versus negativa, ida/retorno separados, revisão esperada, decisão no prazo e aplicação separada da aprovação. | ConfirmPassengerRoute continua **somente legado** até remoção coordenada. Nenhum booleano é reinterpretado como embarque ou intenção nova. |
| 1.5 — viagem/participação | Travel datada, agenda, preparação/revisões, uma viagem por serviço/dia, TravelParticipation, ParticipationEvent e SeatReservation. Horários/estados/duplicidade efetiva protegidos por constraints. | Capacidade agregada, agenda, autorização, correções e concorrência exigem os services. Reserva é proposta de vaga, não segunda participação efetiva. Viagens novas não entram nos endpoints/GPS antigos. |
| 1.6 — percurso/avisos | RouteSnapshot, RouteStop, RouteStopParticipant, TravelPublication, DriverInvitation, Notification; job ligado à revisão base/entrada congelada e token/validade de claim. | Worker legado só pega jobs de Path. Novos campos de claim **não implementam** recuperação/CAS/retries por si só; worker/serviço futuro deverá aplicá-los. Aviso é persistência interna, sem novo e-mail operacional/push/WS. |

### 11.1. Revisões e histórico

- `RouteSnapshot` guarda revisão candidata e revisão base; assim, preparar uma troca
  não precisa alterar a viagem/alocação vigente. Job congela entradas da proposta;
  validação local verifica correspondência. O serviço futuro comparará revisão,
  claim e estado sob lock antes de gravar/aplicar qualquer resultado.
- Snapshots prontos exigem resultado/medidas/instante no banco; `clean` valida medidas
  finitas, geometria LineString e coordenadas. Banco não valida toda a geometria JSON.
  Origin/destination e pontos de parada são dados congelados, não referências mutáveis
  ao perfil. Atualizar configuração não dispara HTTP nem reescreve esses campos.
- Parada tem ordem única no snapshot e associação de vários participantes/operações;
  dois alunos no mesmo ponto não exigem duas coordenadas artificiais. Execução da parada
  tem ator/horário, separada dos eventos de embarque/desembarque de cada aluno.
- Publicação referencia snapshot/revisão e autor/instante, preservando versões anteriores.
  Travel separa snapshot atual/publicado e revisão publicada. Para viagem datada em
  andamento, constraints exigem designações, preparação pronta e ponteiros/revisões
  compatíveis. Validar aptidão/capacidade/aceite do substituto ainda cabe ao serviço.
- Convite identifica o vínculo de motorista, prazo, resposta explícita e versão corrente;
  trocar convite não apaga respostas antigas. Ausência de resposta permanece pendente,
  nunca aceite. Ator convidado e empresa são revalidados localmente e futuramente sob lock.
- Avisos deduplicam por destinatário/chave, têm recurso tipado/ID e leitura separada.
  Validação limita payload a status/revisão; não copia nomes, CPF, endereço ou posição.
  Autorizar recurso/destinatário e gravar decisão+aviso atomicamente são trabalho da Etapa 2.

### 11.2. Segurança da coexistência e encerramento do marco

Migrations novas desta continuação: `router.0008` a `0012`. Não reescreveram arquivos
antigos nem converteram/copiaram/apagaram dados do banco habitual. Constraints novas
podem exigir saneamento de dados legados inválidos antes de aplicação futura; isso
precisa de diagnóstico e autorização, não de descarte automático no startup.

Todos os modelos estruturais novos, incluindo jobs, estão com admin somente leitura.
Veículos empresariais e viagens datadas não podem ser alterados pelo admin antigo;
formulários/serializers legados mantêm driver/path/grupo obrigatórios onde precisavam
continuar assim. REST/WS/GPS e confirmações legados não acessam viagens novas.
Sem endpoints novos nem edição no repositório frontend.

**Conclusão precisa:** o marco estrutural cobre 1.1–1.6 em banco limpo temporário,
mas a substituição integral do domínio antigo **não foi concluída**. Permanecem
CompanyRouteSchedule, ConfirmPassengerRoute, perfil.route_group/flags, campos legados
da frota, Path e caminhos legados documentados na seção 10.2. Seu único caminho de
escrita operacional continua legado; as tabelas novas ficam sem escrita operacional
até migração coordenada de todos os callers nas Etapas 2/3. Não ligar apenas parte
do fluxo novo nem criar sincronização por signals para sustentar dois domínios.

### 11.3. Validações finais desta continuação

- Baseline inicial falhou em um teste por data UTC/local; correção isolada em
  `37b7c03`, com baseline repetido **115/115** (136,356 s).
- Recortes intermediários: 23/23 (serviços/frota + privacidade), 25/25 (transport
  após política/demanda), 46/46 (transport + privacidade após participação) e 50/50
  (transport antes das três regressões finais de planejamento) passaram.
- Suíte final: **168/168**, 215,551 s. Inclui percurso pronto, publicação/ponteiros,
  rejeição de revisão obsoleta em viagem ativa, reserva distinta de alocação,
  várias pessoas na mesma parada, exclusividade por trecho, convites/prazos,
  minimização de avisos, admin protegido e isolamento do worker legado.
- `pdm run lint`: passou, 135 arquivos formatados. Ajustes intermediários de lint
  foram de imports/linhas/formatação. `pdm run check`: sem problemas e sem migration
  de model pendente. `pdm run schema`: validado com `--fail-on-warn`.
- Testes construíram/destruíram banco temporário desde zero com todo o grafo de
  migrations. Shell forçou `DATABASE_URL=sqlite:////tmp/opencode/nextrouter-stage1.sqlite3`,
  Redis/geocodificação/OSRM/SMTP/Cloudinary vazios e documentos em
  `/tmp/opencode/nextrouter-stage1-documents`; schema somente em
  `/tmp/opencode/nextrouter-schema.yaml`. Nenhum migrate no banco habitual.
- Continua aviso de `staticfiles/` ausente. Não executados PostgreSQL/concorrência
  real, Redis multiprocesso, novo worker, navegador/Vue, chamadas externas reais,
  check-deploy ou deploy. SQLite comprova as negações estruturais testadas, **não locks**.
- Documentação Django 6.0 de constraints/validação consultada via Context7; links,
  blocos de código e `git diff --check` conferidos. Sem novos settings/dependências.

## 12. Etapa 2 — serviços transacionais, em andamento

### 12.1. Primeiro recorte 2.1 — solicitação, decisão e retirada de vínculo

**Escopo desta continuação (2026-11-15):** o dono solicitou implementar a Etapa 2.
Iniciado o trabalho independente das decisões pendentes da seção 3.4. Nenhuma
migration, mudança de settings/dependências ou escrita no banco habitual. Não
interpretar este recorte como conclusão da Etapa 2 nem autorização para decidir
os efeitos ainda pendentes de encerramento, regeneração ou execução.

**Implementação:** `modules/organizations/services/memberships.py`, sem dependência
de request/Response, com entradas por IDs (ator usa a PK UUID do usuário) e retorno
de `CompanyMembership`. Erros `MembershipError` são `ValidationError` de domínio,
com mensagem em português e código estável; tradução HTTP fica para a Etapa 3.

| Serviço | Contrato neste recorte |
|---|---|
| `request_membership` | Titular ativo informa exatamente um perfil (aluno/motorista) e empresa aprovada/ativa. Reobtém dados, não considera flags/grupo legados como vínculo novo. Pedido pendente à mesma empresa retorna o ciclo existente; qualquer ciclo ativo ou pendente a outra empresa é conflito. Ciclos terminais permitem novo pedido sem reescrever história. |
| `approve_membership` | Somente usuário titular da empresa aprovada/ativa; revalida titular ativo. Pendente vira ativo com revisor/instante; não exige grupo, aloca viagem nem publica programação. |
| `reject_membership` | Somente usuário titular da empresa aprovada/ativa; pendente vira recusado com revisor/instante. Não encerra vínculo ativo. |
| `withdraw_membership` | Somente titular ativo retira pedido pendente; não exige que a empresa continue aprovada/ativa. Preserva autor/instante; impede decisão posterior. |

- Repetir a mesma decisão/retirada retorna o resultado sem novo evento/aviso nem
  substituição de motivo/instante. Decisão oposta ou transição de estado terminal
  é conflito. Repetições revalidam autorização; staff/superusuário não têm bypass.
- Motivo opcional tem até 500 caracteres e fica apenas no evento; não entra no
  aviso. Relógio anterior à solicitação resulta em erro de domínio sem escrita.
- Ordem **local** de locks: perfil estável → empresa → vínculo existente → usuários
  por PK crescente. O perfil serializa também a ausência de ciclo; não basta
  bloquear pedidos diferentes ou consultar `.exists()`. Inserts de evento/aviso
  pertencem à mesma transação da decisão. A ordem global com viagens/jobs ainda
  precisa ser integrada antes de implementar encerramento/start/publicação.
- Solicitação/retirada notificam a empresa; aprovação/recusa notificam o titular.
  Aviso contém somente status, referência ao ciclo e chave por ciclo/ação. Falha
  na persistência do evento ou aviso desfaz a transição inteira. Sem e-mail, WS,
  chamada externa, signal de espelhamento ou alteração dos perfis legados.

**Coexistência:** serviços novos ainda não são chamados por API/admin/worker.
Admin novo permanece somente leitura e o caminho operacional continua legado.
Este recorte prepara o serviço compartilhado; não habilita outra fonte de verdade.
Não expor ações novas sem substituir coordenadamente os callers da seção 11.2.

**Próximos bloqueios:** encerramento de vínculo e troca de grupo exigem fechar os
efeitos sobre atendimentos/viagens futuros já gerados. Regeneração precisa definir
conflitos sem descartar respostas/alocações e a granularidade do dia parcialmente
publicado. Não implementar uma política silenciosa de cancelamento/transferência.
Os serviços restantes de 2.1 e as subetapas 2.2–2.6 ainda não estão concluídos.

**Evidências desta execução:**

- Baseline anterior à implementação: **168/168 testes**, 166,962 s; lint passou
  (135 arquivos). Ambiente temporário, serviços externos desabilitados.
- Recorte: **18 testes de serviço passaram** (4,178 s para 22 descobertos),
  cobrindo ambos os perfis, autorização/negações, idempotência, estado/horários,
  histórico, efeitos mínimos e rollback por falha de evento/aviso. Quatro testes
  de concorrência preparados com `TransactionTestCase`, threads/conexões distintas,
  barreira inicial e limites de espera; **ignorados em SQLite**, não comprovados.
- Suíte completa: **190 descobertos, 186 passaram e 4 ignorados**, 147,948 s.
  `check` passou, sem mudanças de models; `schema` validou com `--fail-on-warn`,
  sem novos endpoints. Lint teve ajustes intermediários de estilo/formatação.
- Variáveis de shell: `DATABASE_URL=sqlite:////tmp/opencode/nextrouter-stage2.sqlite3`,
  Redis/geocodificação/OSRM/SMTP/Cloudinary vazios, documentos em
  `/tmp/opencode/nextrouter-stage2-documents`. Test runner criou/destruiu seu banco;
  nenhum migrate no banco habitual. Schema só em `/tmp/opencode/nextrouter-schema.yaml`.
- Referência: documentação oficial Django 6.0 de `select_for_update` e testes
  transacionais (consulta direta; ferramentas Context7 indisponíveis na sessão).
- Validação final de estilo: `pdm run lint` passou (139 arquivos formatados).
  Links locais, blocos Markdown e `git diff --check` conferidos, sem problemas.
- Continua o aviso de `staticfiles/` ausente. Sem PostgreSQL, Redis multiprocesso,
  navegador/Vue, worker persistente, chamadas externas reais, check-deploy ou deploy.
  Não declarar validação de concorrência nem entrega operacional deste recorte.
