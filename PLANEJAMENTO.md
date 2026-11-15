# NextRouter — planejamento de adaptação

**Decisões aprovadas em novembro de 2026; registro em 2026-11-15.**

Este é o documento principal de produto, arquitetura-alvo e execução da adaptação.
Para preparar os arquivos compilados do frontend, consulte o tutorial separado
[BUILD_VUE.md](BUILD_VUE.md).
Substitui `docs/DOMINIO.md`, `docs/ARQUITETURA.md`, `docs/DECISOES.md`,
`docs/CONVENCOES.md` e `docs/PROGRESSO.md`. Distinguir sempre **decisão aprovada**,
**proposta técnica a detalhar** e **comportamento já implementado**.

**Estado:** plano registrado; nenhuma etapa de implementação iniciada nesta tarefa.
A aplicação ainda usa o domínio anterior e ainda não serve o build do Vue.
Não interpretar exemplos de modelos, estados, caminhos ou serviços como código existente.

### Como interpretar este documento

- **Aprovado:** fluxo de programação habitual, resposta diária, políticas por grupo,
  prorrogação com aprovação manual, desistência permitida, motorista habitual e aceite
  de substituto, geração semanal, avisos internos, uma empresa por perfil e produção
  Vue/Django na mesma origem. São decisões tomadas com o dono nesta sessão.
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
anterior até o aceite. Aprovar valida vaga e viabilidade e transfere atomicamente,
sem dupla alocação. Se a programação já estiver publicada, a alteração gera revisão
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
- O motorista só inicia/finaliza a viagem designada e se estiver aprovado e apto.
  Empresa aprovada gerencia planejamento e cancelamento pré-início.

### 3.2. Prazos, publicação e revisão

- Respostas livres terminam no prazo normal; solicitações de inclusão/troca terminam
  no fim da prorrogação, se habilitada. A proposta é exigir também aceite dentro
  dela; confirmar essa regra na Etapa 0 (seção 3.4) e então revalidá-la no serviço.
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
| Pedido enviado no prazo pode ser aprovado depois do fim da prorrogação? | Recomendar expiração no fim da janela. A sessão aprovou prazo de prorrogação, mas não distinguiu explicitamente prazo de envio e de decisão. Bloqueia definição final de estados/worker. |
| Pode haver mais de um grupo ativo para um aluno na mesma empresa? | Não confundir uma empresa com um grupo. Se permitir vários grupos, validar conflitos de agenda entre eles; se limitar, registrar a restrição. |
| Pode solicitar outra empresa enquanto possui vínculo ativo? | Preservar vínculo atual até troca explícita; decidir quantidade de pedidos pendentes e encerramento. Não sobrescrever empresa atual com um novo pedido. |
| Alteração de política/programação afeta dias já gerados, ainda abertos? | Recomendar snapshot na geração e ação explícita para futuras datas ainda editáveis, nunca atualização silenciosa de dias publicados. |
| Aprovação de troca com falha no novo cálculo mantém qual alocação? | Recomendar manter a alocação transferida em revisão pendente e exigir resolução da empresa, sem rollback tardio invisível. Confirmar antes de implementar a seção 4.1. |
| Pode publicar cada viagem independentemente ou o dia é publicado em bloco? | Recomendar por viagem, com painel agregado do dia. Uma pendência do meio-dia não deve impedir automaticamente uma ida pronta. |
| Como reorganizar um serviço lotado? | Empresa escolhe passageiros e viagem adicional explicitamente; confirmar suporte a mais de uma viagem por serviço/data antes de definir unicidade. Não adotar ordem de confirmação como prioridade sem decisão. |
| Desistência da ida também cancela retorno? | Recomendar desistência por trecho; ida e volta independentes. Definir interação com pedido pendente e impedir que um aceite antigo reinsira aluno que desistiu. |
| Cancelamento do dia com alguma viagem já iniciada | Não cancelar retroativamente viagens ativas/finalizadas. Confirmar cancelamento apenas das ainda não iniciadas e indicação de cancelamento parcial. |
| Encerrar viagem com aluno ainda marcado como embarcado; erro de marcação | Definir correção auditada e regra de fechamento, sem fabricar desembarque automático. |
| Desaprovação/desativação durante viagem ativa | Definir quem conclui a ocorrência operacional e como controlar acesso; não manter nem bloquear implicitamente ações essenciais sem regra. |
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

### 4.1. Receita técnica para alteração e publicação (proposta)

Esta receita esclarece o trabalho assíncrono; a decisão de negócio sobre falha após
aceite ainda depende da seção 3.4. Não implementar uma transação de banco aberta
durante geocodificação/OSRM.

1. Serviço recebe ator, ID do pedido e revisão esperada; não depende de `request`
   ou `Response` do DRF. Reobtém objetos do banco e valida autorização de domínio.
2. Na transação, bloqueia pedido, participação e viagens envolvidas em ordem
   consistente. Revalida elegibilidade, prazo, execução e capacidade atual.
3. Aceite transfere a participação e atualiza a escolha vigente atomicamente.
   Remove a alocação antiga e ocupa a nova vaga na mesma transação. Uma tentativa
   repetida do mesmo aceite não pode transferir de novo nem duplicar avisos.
4. Incrementa a revisão das viagens afetadas, marca preparação pendente, grava jobs
   com entradas congeladas e avisos mínimos. A decisão aceita é distinta do estado
   do percurso e da publicação; informar “alteração aceita, programação em atualização”.
5. Worker calcula fora dos locks. Na gravação, verifica revisão, estado, cancelamento
   e titularidade do processamento; descarta resultado obsoleto. Falha gera pendência
   observável, nunca sucesso nem reconstrução usando dados atuais de outra revisão.
6. Empresa publica a revisão pronta; grava aviso de publicação. `start` exige que
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
- Geração usa chave única de atendimento `(grupo, data)`. A chave da viagem habitual
  deve distinguir geração automática de viagens adicionais manuais caso estas sejam
  aprovadas; não impor `(serviço, data)` único cegamente.
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

**Marco:** o fluxo SuperTransporte e as exceções têm representação sem contradições;
estados, decisões pendentes e contrato de integração estão explícitos. Documento
de planejamento registrado não significa que toda esta etapa esteja concluída.

### Etapa 1 — Consolidação da modelagem

#### 1.1. Organizações: perfis e vínculo empresarial

- Desacoplar `Passenger`/`Driver` do único `route_group` atual; representar empresa
  e revisão do vínculo independentemente dos grupos. Uma empresa ativa por perfil.
- Preservar identidade do usuário e documentos; empresa encerra vínculo, não apaga
  conta ou histórico do aluno/motorista como se fossem dados de sua propriedade.
- Definir preservação das viagens passadas quando muda vínculo, grupo ou aprovação.

#### 1.2. Grupo, pontos e serviços programados

- Evoluir `CompanyRouteGroup` para atendimento a destino comum com endereço completo.
- Representar participação do passageiro no grupo, ponto habitual e serviços autorizados.
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
- Pedido pendente conserva escolha anterior. Aprovar revalida prazo, vaga,
  pertencimento, agenda, estado e revisão da viagem sob transação; o prazo para
  decisão deve seguir a definição fechada na seção 3.4.
- Transferir retorno numa operação atômica; recusas/expirações preservam o anterior.
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
8. Pedro mantém 17h enquanto pede 12h; aprovação transfere atomicamente; recusa preserva 17h.
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
| Etapa 0 — especificação técnica detalhada e estratégia de migrations | Pendente; fluxo principal aprovado, decisões complementares na seção 3.4. |
| Etapa 1 — modelagem | Não iniciada. |
| Etapa 2 — regras | Não iniciada. |
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
