# Build do Vue.js para entrega pelo backend

Este tutorial complementa [PLANEJAMENTO.md](PLANEJAMENTO.md), especialmente as
Etapas 3 e 4. Os repositórios continuam separados; o **artefato de produção** do
Vue acompanha a publicação do Django, na mesma origem.

> **Estado atual:** o backend ainda não possui integração para servir esse build.
> É possível gerar e preparar o artefato com as instruções abaixo, mas copiar a
> pasta não habilita a aplicação. Roteamento, montagem dos assets e cache serão
> implementados nas etapas previstas. Os caminhos apresentados são o contrato
> proposto e devem ser atualizados aqui se a implementação escolher outro layout.

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
backend é Django. O contrato proposto mantém os assets Vue em `/assets/` e os
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

Os endpoints serão revisados na adaptação; não trate este exemplo como contrato
definitivo. Cookies HttpOnly são enviados pelo navegador, não lidos pelo Vue.
Nas mutações, obter CSRF pelo endpoint de bootstrap e enviar `X-CSRFToken`,
incluindo os fluxos de autenticação conforme o contrato. Não guardar access/refresh
em `localStorage`/`sessionStorage` nem tentar ler os cookies HttpOnly.

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

Contrato proposto: copiar **o conteúdo** de `dist/` para `frontend_dist/` na raiz
do pacote do backend. Exemplo em um checkout de entrega novo, ainda sem essa pasta:

```sh
# Substitua pelos caminhos reais dos dois repositórios.
export FRONTEND_REPO=/caminho/para/frontend
export BACKEND_REPO=/caminho/para/backend
mkdir "$BACKEND_REPO/frontend_dist"
cp -R "$FRONTEND_REPO/dist/." "$BACKEND_REPO/frontend_dist/"
```

O `mkdir` sem `-p` falha se o destino já existir: não sobreponha uma entrega antiga
deixando chunks obsoletos por acidente. Prepare uma nova área de build ou peça
autorização para limpar apenas o artefato gerado. Não apague diretórios amplos.

O resultado esperado é `frontend_dist/index.html`, e não
`frontend_dist/dist/index.html`. Não copiar `node_modules/`, código-fonte, `.env`
ou a pasta `html-template-test/`.

Essa cópia manual serve para entender o processo. Na entrega definitiva, a CI ou
o build de imagem deverá obter uma revisão fixada do frontend, compilar e montar
o artefato automaticamente. Registrar commits do backend e frontend no release;
não baixar uma branch mutável durante o startup do servidor.

Arquivos gerados não devem entrar no Git por padrão. A implementação deverá
adicionar a regra adequada de ignore e garantir que o artefato entre no pacote
ou imagem por um passo explícito de build. Node pode ficar só no estágio de build,
fora do runtime Python.

## 5. O que falta implementar no backend

**Não executar estas mudanças como se já estivessem configuradas.** A Etapa 4
deverá integrar o layout acima, em conjunto com as rotas e segurança da Etapa 3:

1. Servir `frontend_dist/index.html` na raiz e nas rotas válidas da SPA.
2. Montar `/assets/` com os arquivos do build, por WhiteNoise ou mecanismo de
   produção equivalente, preservando os nomes com hash do Vite.
3. Publicar explicitamente arquivos públicos adicionais, como favicon, sem
   transformar qualquer arquivo do repositório em conteúdo público.
4. Manter `/static/` para Django/admin e sua coleta habitual. O atual
   `collectstatic` **não integra automaticamente** `frontend_dist/`.
5. Não fazer dupla renomeação dos assets do Vite pelo manifest do Django sem
   reescrever/testar todas as referências. Escolher uma estratégia única de URLs.
6. Aplicar fallback da SPA apenas à navegação apropriada. `/api/...`, `/admin/...`,
   `/ws/...`, `/assets/...`, `/static/...` e downloads não podem receber HTML da
   SPA quando deveriam retornar erro ou outra resposta.
7. HTML sem cache longo; assets versionados com cache longo/imutável. Respostas
   autenticadas e documentos não entram em cache público.
8. Entregar tudo sob HTTPS/WSS e configurar cookies/CSRF/origins para a mesma origem.
9. Manter documentos privados fora do diretório do Vue e da coleta pública.

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
