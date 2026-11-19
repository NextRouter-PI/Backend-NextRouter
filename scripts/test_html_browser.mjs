// Smoke opcional: Node >=22 + Firefox instalados. Sem npm, driver ou bibliotecas novas.
// Somente banco/perfis temporários próprios; não usa o banco habitual nem chama provedores.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { once } from 'node:events';
import { mkdir, mkdtemp, readFile, rm } from 'node:fs/promises';
import { createServer } from 'node:net';
import { resolve } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';

export async function stopChild(child, timeout = 5000) {
  const finished = () => child.exitCode !== null || child.signalCode !== null;
  if (!child.pid || finished()) return;
  const exited = once(child, 'exit');
  child.kill('SIGTERM');
  await Promise.race([exited, delay(timeout, undefined, { ref: false })]);
  if (!finished()) {
    child.kill('SIGKILL');
    await exited;
  }
}

async function main() {
if (!process.argv.includes('--confirm-fictitious')) throw new Error('Exige --confirm-fictitious.');
if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('Exige Node >=22 já instalado.');
if (spawnSync('firefox', ['--version'], { stdio: 'ignore' }).status !== 0) throw new Error('Exige Firefox já instalado.');
const root = await mkdtemp('/tmp/opencode/nr-html-browser-');
const children = [];
const password = randomBytes(24).toString('hex');
let transport;
let successMessage;
let stage = 'preparação';
const python = resolve('.venv/bin/python');
const freePort = async () => {
  const server = createServer();
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const port = server.address().port;
  await new Promise(done => server.close(done));
  return port;
};
const launch = (command, args, env) => {
  const child = spawn(command, args, { env, stdio: ['ignore', 'pipe', 'pipe'] });
  child.on('error', () => {}); // Startup será recusado pelo timeout, mantendo o finally de limpeza.
  children.push(child);
  return child;
};
const waitFor = async (condition, description) => {
  const end = Date.now() + 20000;
  while (Date.now() < end) {
    try { if (await condition()) return; } catch { /* startup ou navegação em curso */ }
    await delay(100);
  }
  throw new Error(`Timeout: ${description}`);
};

try {
  const port = await freePort();
  const origin = `http://127.0.0.1:${port}`;
  const env = {
    ...process.env, DJANGO_SETTINGS_MODULE: 'app.settings.dev', NEXTROUTER_ENV_FILE: `${root}/empty.env`,
    DATABASE_URL: `sqlite:///${root}/db.sqlite3`,
    REDIS_URL: '', OSRM_URL: '', GEOCODING_URL: '', EMAIL_HOST: '', CLOUDINARY_URL: '',
    PRIVATE_DOCUMENT_ROOT: `${root}/private`, MEDIA_ROOT: `${root}/media`, FRONTEND_URL: origin,
    NEXTROUTER_LAN_HOST: '',
    SECRET_KEY: randomBytes(32).toString('hex'), DEMO_PASSWORD: password, PYTHONDONTWRITEBYTECODE: '1',
  };
  await mkdir(`${root}/private`, { mode: 0o700 });
  // Instalação limpa e dados fictícios. OSRM é fixture APENAS neste preparador.
  const setup = spawnSync(python, ['-'], { env, encoding: 'utf8', input: `
import io, json, django
from datetime import timedelta
from unittest.mock import patch
django.setup()
from django.core.management import call_command
from django.utils import timezone
from modules.organizations.models import Company, Driver, Passenger
from modules.transport.models import ServiceDay
from modules.transport.services.demand import answer_day
from modules.transport.services.planning import close_day, publish_travel
from modules.transport.services.jobs import claim_snapshot_job, process_snapshot_job
call_command('migrate', interactive=False, verbosity=0, stdout=io.StringIO())
call_command('seed_demo_data', confirm_fictitious=True, stdout=io.StringIO())
company = Company.objects.get(user__email='company@fixture.example.invalid')
driver = Driver.objects.get(user__email='driver@fixture.example.invalid')
passenger = Passenger.objects.get(user__email='passenger@fixture.example.invalid')
day = ServiceDay.objects.get()
now = timezone.now()
day.opens_at, day.normal_deadline, day.extension_deadline = now-timedelta(hours=1), now+timedelta(hours=1), now+timedelta(hours=2)
day.save(update_fields=['opens_at', 'normal_deadline', 'extension_deadline'])
eligibility = day.eligibilities.get()
service = day.route_group.services.get(direction='outbound')
answer_day(actor_id=passenger.user_id, eligibility_id=eligibility.pk, outbound_service_id=service.pk, return_service_id=None, expected_revision=0)
day.normal_deadline = now-timedelta(seconds=1)
day.save(update_fields=['normal_deadline'])
close_day(actor_id=company.user_id, day_id=day.pk)
def route(coordinates, **kwargs):
    return {'order': list(range(len(coordinates))), 'geometry': {'type': 'LineString', 'coordinates': coordinates}, 'distance_meters': 1000, 'duration_seconds': 300}
with patch('modules.transport.services.routing.optimize_coordinates', side_effect=route), patch('modules.transport.services.routing.route_coordinates', side_effect=route):
    while (job := claim_snapshot_job(company_id=company.pk, lease_duration=timedelta(seconds=60), max_attempts=1)) is not None:
        process_snapshot_job(job_id=job.pk, claim_token=job.claim_token, max_attempts=1, retry_delay=timedelta(seconds=1))
travel = day.travels.get(service=service)
publish_travel(actor_id=company.user_id, travel_id=travel.pk, expected_revision=travel.revision)
print(json.dumps({'travel_id': travel.pk, 'service_id': service.pk, 'group_id': day.route_group_id, 'driver_id': driver.pk}))
` });
  assert.equal(setup.status, 0, 'Falha ao preparar a fixture isolada (nenhum banco habitual foi usado).');
  const fixture = JSON.parse(setup.stdout.trim());
  const web = launch(python, ['-m', 'daphne', '-b', '127.0.0.1', '-p', String(port), '--access-log', '/dev/null', 'app.asgi:application'], env);
  // Consumir sem imprimir: nada de access log, credenciais ou respostas no console.
  web.stdout.on('data', () => {});
  web.stderr.on('data', () => {});
  await waitFor(async () => (await fetch(`${origin}/health/live/`)).ok, 'servidor ASGI local');

  stage = 'Firefox';
  await mkdir(`${root}/firefox`);
  const debuggingPort = await freePort();
  const firefox = launch('firefox', ['--headless', '--no-remote', '--profile', `${root}/firefox`, '--remote-debugging-port', String(debuggingPort)], env);
  let announced = false;
  firefox.stderr.on('data', data => { if (data.toString().includes('WebDriver BiDi listening')) announced = true; });
  firefox.stdout.on('data', () => {});
  await waitFor(() => announced, 'agente BiDi do Firefox');
  transport = new WebSocket(`ws://127.0.0.1:${debuggingPort}/session`);
  await once(transport, 'open');
  let sequence = 0;
  const pending = new Map();
  transport.addEventListener('message', ({ data }) => {
    const message = JSON.parse(data);
    const callback = pending.get(message.id);
    if (!callback) return;
    pending.delete(message.id);
    if (message.type === 'error') callback.reject(new Error(`BiDi: ${message.error}`));
    else callback.resolve(message.result);
  });
  const command = (method, params) => new Promise((done, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Timeout BiDi: ${method}`)); }, 25000);
    pending.set(id, { resolve: value => { clearTimeout(timer); done(value); }, reject: error => { clearTimeout(timer); reject(error); } });
    transport.send(JSON.stringify({ id, method, params }));
  });
  await command('session.new', { capabilities: {} });
  // Confirmações aceitas somente pelo harness, nunca pelo código servido.
  await command('script.addPreloadScript', { functionDeclaration: `() => {
    window.confirm = () => true;
    window.__csrfFailures = [];
    window.__socketOpens = 0;
    const NativeSocket = window.WebSocket;
    window.WebSocket = class extends NativeSocket {
      constructor(...args) { super(...args); this.addEventListener('open', () => window.__socketOpens++); }
    };
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (...args) => {
      const response = await nativeFetch(...args);
      if (response.status === 403) {
        try { window.__csrfFailures.push((await response.clone().json()).detail); } catch {}
      }
      return response;
    };
  }` });
  const evaluate = async (context, expression) => {
    // Falhar cedo se a expressão do próprio harness estiver malformada.
    new Function(`return (${expression});`);
    const result = await command('script.evaluate', { expression, target: { context }, awaitPromise: true, resultOwnership: 'none' });
    if (result.type !== 'success') throw new Error('Exceção no script da página (valores não registrados).');
    return result.result.value;
  };
  const ready = context => waitFor(() => evaluate(context, 'Boolean(document.querySelector("#session button"))'), 'inicialização da página');
  const navigate = async (context, file) => {
    await command('browsingContext.navigate', { context, url: `${origin}/html-template-test/${file}`, wait: 'complete' });
    await ready(context);
  };
  const click = (context, text) => evaluate(context,
    `(() => { const node = [...document.querySelectorAll('button')].find(item => item.textContent === ${JSON.stringify(text)}); if (!node) throw new Error('Botão ausente'); node.click(); return true; })()`);
  const login = async role => {
    const { userContext } = await command('browser.createUserContext', {});
    const { context } = await command('browsingContext.create', { type: 'tab', userContext });
    await navigate(context, 'index.html');
    await evaluate(context, `(() => { const form = document.querySelector('#workspace form'); form.elements.email.value = ${JSON.stringify(`${role}@fixture.example.invalid`)}; form.elements.password.value = ${JSON.stringify(password)}; form.requestSubmit(); return true; })()`);
    try {
      await waitFor(() => evaluate(context, `document.querySelector('#session').textContent.includes(${JSON.stringify(`${role}@fixture.example.invalid`)})`), `login ${role}`);
    } catch {
      const diagnostic = await evaluate(context, `(async () => JSON.stringify({status: [...document.querySelectorAll('[role=status]')].map(item => item.textContent), csrf: window.__csrfFailures, apiStatus: await fetch('/api/users/me/').then(response => response.status)}))()`);
      throw new Error(`Login não concluído: ${diagnostic}`);
    }
    return context;
  };

  stage = 'login, recarga, formulários e seleção habitual';
  const company = await login('company');
  await navigate(company, 'index.html');
  assert.equal(await evaluate(company, "document.querySelector('#session').textContent.includes('company@fixture.example.invalid')"), true);
  await navigate(company, 'grupos-horarios.html');
  await click(company, 'Carregar grupos');
  try {
    await waitFor(() => evaluate(company, `document.querySelector('select[aria-label="Grupo de atendimento"]').options.length > 1`), 'grupos');
  } catch {
    const statuses = await evaluate(company, `(async () => { const response = await fetch('/api/company-route-groups/'); const data = await response.json(); return JSON.stringify({status: response.status, records: data.results?.length, options: [...document.querySelectorAll('select')].map(item => ({label: item.getAttribute('aria-label'), count: item.options.length})), messages: [...document.querySelectorAll('[role=status]')].map(item => item.textContent)}); })()`);
    throw new Error(`Grupos não carregados: ${statuses}`);
  }
  await evaluate(company, `document.querySelector('select[aria-label="Grupo de atendimento"]').value = '${fixture.group_id}'`);
  await click(company, 'Carregar serviços do grupo');
  await waitFor(() => evaluate(company, `document.querySelector('select[aria-label="Serviço habitual"]').options.length > 1`), 'serviços');
  await evaluate(company, `document.querySelector('select[aria-label="Serviço habitual"]').value = '${fixture.service_id}'`);
  await click(company, 'Carregar alunos e seleção atual');
  await waitFor(() => evaluate(company, "document.querySelectorAll('#workspace input[type=checkbox]').length === 1"), 'alunos');
  assert.equal(await evaluate(company, "document.querySelector('#workspace input[type=checkbox]').checked"), true);
  for (const selected of [false, true]) {
    await evaluate(company, `document.querySelector('#workspace input[type=checkbox]').checked = ${selected}`);
    await click(company, 'Salvar somente alterações selecionadas');
    await waitFor(() => evaluate(company, `document.querySelector('#workspace').textContent.includes('Processamento encerrado') && ![...document.querySelectorAll('button')].find(item => item.textContent === 'Salvar somente alterações selecionadas').disabled`), 'salvamento individual');
    await click(company, 'Carregar alunos e seleção atual');
    await waitFor(() => evaluate(company, "document.querySelectorAll('#workspace input[type=checkbox]').length === 1"), 'releitura da seleção');
    assert.equal(await evaluate(company, "document.querySelector('#workspace input[type=checkbox]').checked"), selected);
  }
  await click(company, 'Cadastre serviços habituais');
  await evaluate(company, `document.querySelector('form select[aria-label="Grupo de atendimento"]').closest('fieldset').querySelector('button').click()`);
  await waitFor(() => evaluate(company, `document.querySelector('form select[aria-label="Grupo de atendimento"]').options.length > 1`), 'escolhas relacionadas do formulário');

  const metadata = JSON.parse(await readFile('html-template-test/assets/workflows.json', 'utf8'));
  for (const page of metadata.pages) {
    await navigate(company, page.file);
    assert.equal(await evaluate(company, 'document.querySelectorAll("style, [style], link[rel=stylesheet]").length'), 0);
  }
  await navigate(company, 'painel.html');
  const count = await evaluate(company, `document.querySelector('select[aria-label="Operação HTTP"]').options.length`);
  assert.ok(count > 100);
  for (let index = 0; index < count; index++) {
    await evaluate(company, `document.querySelector('select[aria-label="Operação HTTP"]').value = '${index}'`);
    await click(company, 'Abrir formulário técnico');
    assert.equal(await evaluate(company, 'document.querySelectorAll("#workspace section form").length'), 1);
  }

  stage = 'início real pelo formulário e WebSocket em contextos separados';
  const driver = await login('driver');
  const passenger = await login('passenger');
  await navigate(driver, 'viagens-presenca.html');
  await click(driver, 'Carregar / atualizar registros');
  await waitFor(() => evaluate(driver, 'document.querySelectorAll("#workspace table tbody tr").length > 0'), 'viagens');
  await evaluate(driver, `(() => { const row = [...document.querySelectorAll('#workspace table tbody tr')].find(item => item.cells[0].textContent === '${fixture.travel_id}'); row.querySelector('button').click(); return true; })()`);
  await waitFor(() => evaluate(driver, "[...document.querySelectorAll('button')].some(item => item.textContent === 'Inicie a viagem designada')"), 'ação de início');
  await click(driver, 'Inicie a viagem designada');
  await evaluate(driver, "document.querySelector('#workspace form h3').closest('form').requestSubmit()");
  await waitFor(() => evaluate(driver, "document.querySelector('#workspace').textContent.includes('Operação concluída')"), 'início');
  for (const context of [driver, passenger]) {
    await navigate(context, 'ws-localizacao.html');
    await click(context, 'Carregar viagens em andamento');
    await waitFor(() => evaluate(context, `document.querySelector('select[aria-label="Viagem em andamento"]').options.length > 1`), 'viagem ativa');
    await evaluate(context, `document.querySelector('select[aria-label="Viagem em andamento"]').value = '${fixture.travel_id}'`);
    await click(context, 'Conectar WebSocket');
    await waitFor(() => evaluate(context, "document.querySelector('#workspace').textContent.includes('Conectado;')"), 'socket autenticado');
  }
  assert.equal(await evaluate(passenger, 'document.querySelector("#workspace form fieldset").disabled'), true);
  assert.equal(await evaluate(driver, 'document.querySelector("#workspace form fieldset").disabled'), false);
  await evaluate(driver, `(() => { document.querySelector('input[aria-label="Latitude"]').value = '-26.3'; document.querySelector('input[aria-label="Longitude"]').value = '-48.8'; document.querySelector('#workspace form').requestSubmit(); return true; })()`);
  await waitFor(() => evaluate(passenger, "document.querySelector('#workspace output').textContent.includes('-26.3')"), 'posição entregue ao aluno');

  stage = 'CSRF, renovação e logout';
  assert.equal(await evaluate(passenger, "fetch('/api/notifications/1/read/', {method:'POST', credentials:'same-origin'}).then(response => response.status)"), 403);
  const opened = await evaluate(driver, 'window.__socketOpens');
  await click(driver, 'Renovar sessão');
  await waitFor(() => evaluate(driver, `window.__socketOpens > ${opened} && document.querySelector('#workspace').textContent.includes('Conectado;')`), 'reconexão após refresh');
  await click(passenger, 'Sair');
  await waitFor(() => evaluate(passenger, "document.querySelector('#session').textContent.includes('Não autenticado')"), 'logout');
  assert.equal(await evaluate(driver, "document.querySelector('#session').textContent.includes('driver@fixture.example.invalid')"), true);
  successMessage = `Smoke Firefox aprovado: ${metadata.pages.length} páginas, ${count} formulários, cookies/CSRF, perfis isolados, início e WS. Recursos próprios removidos. OSRM somente fixture; sem TLS/provedor/Vue.`;
} catch (error) {
  console.error(`Smoke HTML falhou na fase: ${stage}. ${error.message}`);
  process.exitCode = 1;
} finally {
  transport?.close();
  for (const child of children.reverse()) await stopChild(child);
  await rm(root, { recursive: true, force: true });
}
if (successMessage && !process.exitCode) console.log(successMessage);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
