# Build do Vue.js para entrega pelo backend

Este tutorial complementa [PLANEJAMENTO.md](PLANEJAMENTO.md), especialmente as
Etapas 3 e 4. Os repositórios continuam separados; o **artefato de produção** do
Vue acompanha a publicação do Django, na mesma origem.

> **Estado atual:** a Etapa 3 implementou roteamento, assets isolados, cache seguro
> e autenticação de mesma origem no backend. O layout abaixo já é reconhecido.
> Isso **não comprova integração real**: frontend separado, build reproduzível,
> pipeline de publicação e testes em navegador continuam no marco conjunto 3/4.
> Contrato HTTP/WS em [CONTRATO_API.md](CONTRATO_API.md).
> Preparação/verificação de artefato e runtime local descritos em [OPERACAO.md](OPERACAO.md).

## 1. Conferir o projeto frontend

No repositório Vue, confira `package.json`, o lockfile e a versão de Node definida
pelo projeto (`engines`, `.nvmrc` ou equivalente). Use essa versão de Node e o
gerenciador de pacotes correspondente.

Os exemplos seguintes pressupõem **Vue com Vite**, npm, `package-lock.json` e
script `build` que executa o build de produção do Vite. Se o projeto usa pnpm,
Yarn ou Vue CLI, adapte os comandos conforme sua configuração; não crie outro
lockfile nem troque a ferramenta apenas para seguir este tutorial.

## 2. Usar caminhos da mesma origem

Em produção, a aplicação será aberta na raiz, por exemplo:

```text
https://nextrouter.provedor.com/            Vue
https://nextrouter.provedor.com/api/        API
wss://nextrouter.provedor.com/ws/...        WebSocket
```

No Vite, preserve as opções/plugins já existentes e configure `base: '/'`. Não
aponte para o domínio antigo da API nem use `/static/` como base só porque o
backend é Django. O contrato atual mantém os assets Vue em `/assets/` e os
estáticos do Django/admin em `/static/`.

```js
// Trecho ilustrativo de vite.config.js/ts; não substitua o arquivo inteiro.
export default defineConfig({
  // ...plugins e demais opções existentes
  base: '/',
})
```

O exemplo pressupõe que `defineConfig` já esteja importado de `vite` no arquivo.
Se houver Vue Router com history, a aplicação continua na raiz; a recarga das
rotas depende do fallback HTML descrito na seção 5.

Para chamadas HTTP, utilize `/api/...`, não uma URL fixa de outro host. No
contrato atual, por exemplo:

```js
const response = await fetch('/api/users/me/', {
  credentials: 'same-origin',
})
```

Os endpoints vigentes estão em [CONTRATO_API.md](CONTRATO_API.md) e no OpenAPI;
este exemplo não substitui o contrato. Cookies HttpOnly são enviados pelo navegador,
não lidos pelo Vue.
Nas mutações, obter CSRF pelo endpoint de bootstrap e enviar `X-CSRFToken`,
incluindo os fluxos de autenticação conforme o contrato. Não guardar access/refresh
em `localStorage`/`sessionStorage` nem tentar ler os cookies HttpOnly.

Token CSRF e JWT são diferentes: o bootstrap pode devolver o primeiro ao JavaScript;
access/refresh ficam apenas em cookies. A aplicação precisa tratar recarga/expiração
consultando a sessão e renovando conforme o contrato, sem depender de token em memória
para identificar o login. Coordenar renovações concorrentes entre abas/requisições;
não repetir automaticamente uma mutação de negócio sem garantia de idempotência.

Para WebSocket, derive o protocolo e o host da página (`https` → `wss`) e utilize
o caminho do contrato. Não coloque JWT na URL.

**Segredos nunca entram no build:** tudo que o código frontend consome, inclusive
variáveis `VITE_*`, pode ficar público. Não incluir SECRET_KEY, credenciais de banco,
SMTP, Redis, tokens privados ou endereços/dados reais de alunos. Revisar também os
arquivos de `public/`, que podem ser copiados diretamente para o resultado.

## 3. Gerar o build

Execute **no repositório frontend**, numa revisão conhecida e sem reutilizar
artefatos antigos:

```sh
npm ci
npm run build
```

Se não houver lockfile ou script `build`, resolva isso no frontend antes de
prosseguir. A saída padrão do Vite é `dist/`; confirme se `build.outDir` a altera.
Um resultado típico é:

```text
dist/
  index.html
  assets/
    index-<hash>.js
    index-<hash>.css
  favicon.ico                 # se existir no projeto
```

Confira se o HTML referencia `/assets/...`, se chunks carregados sob demanda estão
presentes e se imagens/fontes usam os caminhos corretos. Não remova hashes dos
nomes. Não publique source maps sem decisão explícita.

`npm run preview`, quando configurado para `vite preview`, pode ajudar a inspecionar
o build localmente, mas **não é servidor de produção** nem comprova integração com
cookies, CSRF, API e WebSocket do Django.

## 4. Preparar o artefato para o backend

Contrato implementado: preparar **o conteúdo** de `dist/` como `frontend_dist/`,
com manifesto de identidade **fora** dessa pasta. No backend, usando revisões Git
completas (não nomes de branch/tag):

```sh
# Informe caminhos e hashes completos da entrega, sem segredos.
pdm run prepare-frontend --source "$FRONTEND_REPO/dist" \
  --destination "$NEW_RELEASE_ARTIFACT" \
  --frontend-revision "$FRONTEND_REVISION" --backend-revision "$BACKEND_REVISION"
pdm run verify-frontend --root "$NEW_RELEASE_ARTIFACT/frontend_dist" \
  --backend-revision "$BACKEND_REVISION"
```

`NEW_RELEASE_ARTIFACT` deve ser uma pasta nova, fora da origem. A ferramenta recusa
destino existente, symlinks, ocultos, mapas, manifestos públicos e arquivos fora da
allowlist; confere recursos referenciados pelo HTML e hashes SHA-256 sem renomear
chunks. O manifesto é gravado por último; uma cópia interrompida é recusada na
verificação, sem limpar automaticamente o destino. Não apague diretórios amplos.

O resultado é `frontend_dist/index.html` e `frontend-release.json` como irmãos na
pasta de entrega, nunca `frontend_dist/dist/index.html`. A preparação não executa
npm/Node e não prova que o build corresponde ao código informado: a CI precisa
obter e compilar a revisão fixada de forma confiável. Não incluir `node_modules/`,
código-fonte, `.env` ou `html-template-test/` no artefato.

Em um checkout **novo e limpo** do backend na revisão identificada, montar os dois
resultados preparados na raiz do contexto Docker, sem sobrepor entrega antiga.
O target `release` exige ambos e valida revisão/hashes durante o build. A CI futura
deve automatizar esse passo, registrar commits/digest da imagem e publicar/reverter
a imagem conjunta. Não baixar branch mutável durante startup nem instalar Node no
runtime Python. Detalhes de ambiente e limites reais em OPERACAO.md.

Arquivos gerados não entram no Git (`/frontend_dist/` e `/frontend-release.json` ignorados). A entrega
deve garantir que o artefato entre no pacote ou imagem por passo explícito de build.
Node pode ficar só no estágio de build, fora do runtime Python.

## 5. Contrato implementado no backend e pendências de entrega

- `frontend_dist/index.html` atende GET/HEAD com `Accept: text/html`, sem renderização
  Django. Deep links sem extensão recebem HTML; rota desconhecida da UI tem 200 e
  precisa ser tratada pelo 404 do Vue. Sem build, retorna 404.
- `/assets/` é servido por WhiteNoise sem passar pelo manifest Django. Somente
  extensões de código/imagem/fonte aprovadas; sem source maps, arquivos ocultos,
  manifestos JSON ou symlinks. Arquivo público adicional aprovado: `/favicon.ico`.
- `/static/` continua exclusivo da coleta Django/admin. `collectstatic` não copia
  o Vue nem publica `html-template-test/`, mídia privada ou o repositório.
- Prefixos reservados, arquivos inexistentes, requisições JSON e POST desconhecido
  nunca recebem fallback HTML. API/admin e respostas com cookies são `private, no-store`.
- HTML usa `no-cache`; assets/favicons usam revalidação por ETag/Last-Modified. Não
  se presume fingerprint por regex de nome. Cache longo/imutável só deverá ser
  habilitado quando o pipeline real comprovar versionamento/retenção dos assets.
- Produção exige `PUBLIC_ORIGIN=https://host[:porta]`, sem barra final, com host em
  `ALLOWED_HOSTS`. CORS vazio, cookies Lax/HttpOnly/Secure e allowlists WS/CSRF
  independentes. Não mudar isso para contornar integração.

**Ainda pendente na Etapa 4:** compilar/revisar o artefato real, incluí-lo na imagem
ou release, validar HTTPS/WSS/proxy/storage no provedor, coordenar rollback/API e
testar o Vue em navegador. A referência Docker local passou pelo smoke com fixture
(planejamento 14.3); nenhum build Vue real foi executado nesta implementação.

### Orientação de implementação para agentes

- Same-origin significa mesmo esquema, host e porta pública. Dois processos atrás
  do mesmo host são compatíveis; chamar a API pela URL interna do provedor não é.
- Servir `index.html` como artefato, sem renderizar acidentalmente expressões Vue
  como templates Django. Não criar um template por página Vue.
- Definir fallback explicitamente para GET/HEAD de navegação HTML e rotas da SPA.
  Excluir prefixos reservados também sem barra final (`/api`, `/admin`, `/assets`),
  `/media`, downloads e arquivos públicos ausentes. POST desconhecido não recebe SPA.
  Testar deep links e 404 com/sem barra, conteúdo JSON e arquivos sem extensão.
- Se usar fallback amplo para navegação HTML, documentar que a página Vue pode
  mostrar seu próprio 404; isso não autoriza mascarar 404 de API/assets. O contrato
  de status para rotas desconhecidas da UI deve ser acordado com o frontend.
- Não montar toda `frontend_dist/` como raiz pública sem filtrar seu conteúdo.
  Permitir apenas assets e arquivos públicos aprovados; negar caminhos ocultos,
  traversal, source maps não autorizados e arquivos de manifesto internos.
- Preservar hashes emitidos pelo Vite. Django/admin podem continuar usando seu próprio
  manifest em `/static/`. Se o mecanismo escolhido exigir outro prefixo público,
  ajustar `base`, referências, router e testes juntos; o layout acima já é reconhecido.
- Só assets realmente versionados devem receber cache imutável na entrega futura. Favicon ou arquivo de
  `public/` com nome fixo precisa revalidar. HTML pode usar `no-cache` para revalidação;
  respostas sensíveis exigem política própria, em geral `private, no-store`.
- Build limpo não significa remover indiscriminadamente assets de releases anteriores
  ainda usados por abas abertas. Definir retenção curta por versão ou recuperação
  de erro de chunk com recarga controlada; não criar loop de reload nem misturar
  manualmente arquivos antigos no novo artefato.
- Não registrar service worker/PWA por padrão: cache offline pode guardar respostas
  privadas ou HTML incompatível com a API. Se já existir no Vue, inventariá-lo e
  revisar cache e atualização antes de declarar integração concluída.
- Cookies de access precisam alcançar `/ws/` e `/api/`. CORS pode ficar vazio em
  produção, mas a origem pública ainda deve ser aceita pelo validador do WebSocket.
  Não remover a allowlist WS junto com a configuração cross-origin antiga.
- O teste da integração real é marco conjunto das Etapas 3 e 4. Uma fixture HTML
  valida roteamento do backend, mas não prova funcionamento do Vue real.

Não usar `runserver`, servidor Vite dev ou `vite preview` como servidor de produção.
O processo ASGI atual é Daphne; o mecanismo escolhido para os estáticos deve ser
validado com esse deploy real, não apenas em modo DEBUG.

## 6. Conferir antes de publicar

Depois que a integração estiver implementada, testar em homologação:

- `/` abre o Vue; recarregar uma rota como `/viagens/123` continua funcionando.
- `/api/rota-inexistente/` retorna erro de API, não `index.html`.
- `/assets/arquivo-inexistente.js` retorna 404, não HTML com status 200.
- Login, recarga da página, refresh e logout funcionam com cookies de terceiros bloqueados.
- JWT não aparece no JSON de autenticação, storage do navegador, URL ou logs.
- Mutações sem CSRF válido são rejeitadas; origem indevida não abre WebSocket.
- Acompanhamento funciona em WSS; revogação/encerramento encerram o acesso.
- Downloads privados continuam exigindo autorização.
- Um release novo carrega seus chunks; HTML antigo não fica preso em cache longo.
- Frontend/API são publicados e revertidos em versões compatíveis.
- Nenhum segredo, cliente manual legado ou arquivo privado é servido publicamente.

No desenvolvimento cotidiano, Vue pode continuar no servidor local com hot reload.
Preferir proxy de desenvolvimento para `/api/` e `/ws/`, ou origens locais
explicitamente autorizadas, sem enfraquecer a configuração de produção.

## Referências

- [Vite — build e caminhos públicos](https://vite.dev/guide/build.html)
- [Vite — entrega estática e limites do preview](https://vite.dev/guide/static-deploy.html)
- [WhiteNoise — integração Django e limites para uploads](https://whitenoise.readthedocs.io/en/latest/django.html)

**Validação deste tutorial:** documentação conferida contra as bibliotecas e o
backend atual. O repositório Vue não foi inspecionado e nenhum comando npm/build
ou deploy foi executado nesta tarefa; ferramentas e configuração do frontend
precisam ser confirmadas antes da execução.

Na revisão de ambiguidades de 2026-11-15, o bloco manual então existente na seção 4 foi testado
com arquivos fictícios em diretório temporário: a primeira execução copiou o HTML;
a segunda falhou sem sobrescrevê-lo. Isso valida a proteção do exemplo de shell,
não o build ou o deploy real.

Na Etapa 4, o preparador/verificador substitui o bloco manual: testa identidade,
hashes, allowlist, referências, recusa de sobreposição e adulteração com fixtures.
Isso ainda não comprova o build Vue real ou a integração em navegador.

Na Etapa 3, fixtures fictícias validaram deep links/HEAD, expressões Vue sem
interpolação, prefixos reservados/Accept, cache, ETag e negação de mapas/ocultos/
symlinks. Isso valida o backend, não a compilação, as rotas efetivas ou o navegador
do frontend real.
