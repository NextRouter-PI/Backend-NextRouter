import { collection, errorText, identity, invalidateCsrf, refreshSession, request, sessionEvents } from './client.js';
import { button, element, label, operationForm, recordLabel, resolve, showData } from './forms.js';
import { habitualSelector } from './habitual.js';
import { locationPanel } from './location.js';

const workspace = document.getElementById('workspace');
const session = document.getElementById('session');
let account = null;
let loadedIdentity = false;
let schema;

function role(name) { return Boolean(account?.profiles[name]); }

function allowed(resource, action, method) {
  if (method === 'GET') return true;
  if (resource === 'companies' && method === 'POST') return true;
  if (['passengers', 'drivers'].includes(resource)) return method === 'POST' || role(resource);
  if (resource === 'memberships') {
    if (['approve', 'reject', 'assign-group'].includes(action)) return role('companies');
    return role('companies') || role('passengers') || role('drivers');
  }
  if (resource === 'eligibilities') return role('passengers');
  if (resource === 'change-requests') return action === 'withdraw' ? role('passengers') : role('companies');
  if (resource === 'travels') return role(['start', 'finish', 'unavailability'].includes(action) ? 'drivers' : 'companies');
  if (resource === 'driver-invitations') return role('drivers');
  if (resource === 'travel-participations') return role(action === 'record' ? 'drivers' : 'companies');
  if (resource === 'route-stops') return role('drivers');
  if (resource === 'driver-ratings') return role('passengers');
  if (resource === 'lost-items') return action === 'transition' ? role('companies') : role('passengers') || role('drivers');
  if (resource === 'notifications' || resource === 'sessions') return Boolean(account);
  return role('companies');
}

function appendResult(parent, title, action) {
  const status = element('p', '', { role: 'status' });
  const control = button(title, async () => {
    control.disabled = true;
    try { await action(); status.textContent = 'Concluído.'; }
    catch (error) { status.textContent = errorText(error); }
    finally { control.disabled = false; }
  });
  parent.append(control, status);
}

async function updateSession() {
  const previous = account?.user.id;
  const wasLoaded = loadedIdentity;
  try { account = await identity(); }
  catch (error) {
    account = null;
    if (![401, 403].includes(error.status)) {
      session.replaceChildren(element('h2', 'Sessão'), element('p', errorText(error)));
      return;
    }
  }
  loadedIdentity = true;
  if (wasLoaded && previous !== account?.user.id) { workspace.replaceChildren(); location.reload(); return; }
  session.replaceChildren(element('h2', 'Sessão real da API'));
  session.append(element('p', account
    ? `${account.user.name} — ${account.user.email}. Perfis: ${Object.keys(account.profiles).join(', ') || 'conta sem perfil operacional'}.`
    : 'Não autenticado. Entre na página inicial.'));
  appendResult(session, 'Renovar sessão', async () => { await refreshSession({ manual: true }); await updateSession(); });
  appendResult(session, 'Atualizar sessão e CSRF', async () => { invalidateCsrf(); await updateSession(); });
  appendResult(session, 'Sair', async () => { await request('POST', '/api/me/logout/'); });
}

function login() {
  const form = element('form', null, { method: 'post' });
  form.append(element('h2', 'Entrar'));
  const emailLabel = element('label', 'E-mail: ');
  const email = element('input', null, { type: 'email', name: 'email', required: '', autocomplete: 'username' });
  const passwordLabel = element('label', 'Senha: ');
  const password = element('input', null, { type: 'password', name: 'password', required: '', autocomplete: 'current-password' });
  emailLabel.append(email);
  passwordLabel.append(password);
  const submit = element('button', 'Entrar nesta conta', { type: 'submit' });
  const status = element('p', '', { role: 'status' });
  form.append(emailLabel, ' ', passwordLabel, ' ', submit, status);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    submit.disabled = true;
    try { await request('POST', '/api/login/', { body: { email: email.value, password: password.value } }); }
    catch (error) { status.textContent = errorText(error); }
    finally { password.value = ''; submit.disabled = false; }
  });
  workspace.append(form, element('p', 'Cookies são compartilhados entre abas. Para empresa, motorista e aluno simultâneos, use perfis de navegador separados. Não há troca fictícia de papel.'));
}

function seedFor(record, document, method, path) {
  const content = document.paths[path][method.toLowerCase()].requestBody?.content;
  const fields = resolve(document, content?.['application/json']?.schema || {}).properties || {};
  const seed = {};
  for (const name of Object.keys(fields)) {
    if (record[name] !== undefined) seed[name] = record[name];
    else if (name.endsWith('_id') && record[name.slice(0, -3)] !== undefined) seed[name] = record[name.slice(0, -3)];
  }
  if ('expected_revision' in fields) seed.expected_revision = record.revision;
  if (path.includes('/eligibilities/')) {
    seed.expected_revision = record.response?.revision || 0;
    if (record.response?.answered_at) {
      seed.outbound_service_id = record.response.outbound_service;
      seed.return_service_id = record.response.return_service;
    }
  }
  return seed;
}

async function actionSeed(record, method, path) {
  if (path.endsWith('/automation/')) {
    try {
      const { data } = await request('GET', path.replace('{id}', record.id).replace('/automation/', '/automation-status/'));
      return { ...data, expected_revision: data.revision };
    } catch (error) {
      if (error.status === 404) return { expected_revision: 0 };
      throw error;
    }
  }
  if (path.endsWith('/policy/')) {
    const { data } = await request('GET', `/api/response-policies/?route_group=${encodeURIComponent(record.id)}`);
    return data.results[0] || {};
  }
  return seedFor(record, schema, method, path);
}

function resourceSection(parent, resource, metadata) {
  const path = `/api/${resource}/`;
  const listOperation = schema.paths[path]?.get;
  if (!listOperation) return;
  const section = element('section');
  section.append(element('h2', listOperation.summary || resource));
  const controls = element('p');
  const status = element('p', 'Carregue os registros autorizados para esta conta.', { role: 'status' });
  const tableArea = element('div');
  const detailArea = element('div');
  let currentPage = 1;
  let filter = '';

  const openRecord = async record => {
    detailArea.replaceChildren();
    const detailPath = Object.keys(schema.paths).find(value => new RegExp(`^/api/${resource}/\\{[^}]+\\}/$`).test(value));
    let current = record;
    if (detailPath && schema.paths[detailPath].get) {
      current = (await request('GET', detailPath.replace(/\{[^}]+\}/, encodeURIComponent(record.id)))).data;
    }
    detailArea.append(element('h3', recordLabel(current)));
    const dataArea = element('div');
    showData(dataArea, current);
    detailArea.append(dataArea);
    const actions = element('p');
    const formArea = element('div');
    for (const [target, methods] of Object.entries(schema.paths)) {
      if (!new RegExp(`^/api/${resource}/\\{[^}]+\\}/`).test(target)) continue;
      const action = target.split('/')[4] || '';
      for (const method of ['GET', 'POST', 'PATCH', 'PUT', 'DELETE']) {
        const operation = methods[method.toLowerCase()];
        if (!operation || (method === 'GET' && target === detailPath) || !allowed(resource, action, method)) continue;
        // PUT fica no painel; o fluxo do site prefere PATCH explícito de identidade.
        if (method === 'PUT') continue;
        const control = button(operation.summary || action || method, async () => {
          control.disabled = true;
          try {
            const seed = await actionSeed(current, method, target);
            formArea.replaceChildren();
            const params = Object.fromEntries([...target.matchAll(/\{([^}]+)\}/g)].map(match => [match[1], current.id]));
            operationForm(formArea, schema, method, target, {
              seed, params, context: current,
              onSuccess: method === 'GET' ? undefined : async () => { await load(currentPage); },
            });
          } catch (error) { status.textContent = errorText(error); }
          finally { control.disabled = false; }
        });
        actions.append(control, ' ');
      }
    }
    detailArea.append(actions, formArea);
  };

  const load = async page => {
    status.textContent = 'Consultando…';
    tableArea.replaceChildren();
    try {
      const data = await collection(path + filter, page);
      if (!Array.isArray(data.results)) throw new Error('Lista inválida.');
      currentPage = page;
      status.textContent = `Página ${page} de ${data.total_pages || 1}. ${data.results.length} registros nesta página.`;
      const columns = metadata.columns[resource] || Object.keys(data.results[0] || {}).slice(0, 6);
      const table = element('table');
      const head = element('tr');
      for (const name of columns) head.append(element('th', label(name), { scope: 'col' }));
      head.append(element('th', 'Ações', { scope: 'col' }));
      const thead = element('thead');
      thead.append(head);
      const tbody = element('tbody');
      for (const row of data.results) {
        const tr = element('tr');
        for (const name of columns) tr.append(element('td', typeof row[name] === 'object' ? JSON.stringify(row[name]) : row[name]));
        const cell = element('td');
        cell.append(button('Abrir e escolher ação', async () => {
          try { await openRecord(row); }
          catch (error) { status.textContent = errorText(error); }
        }));
        tr.append(cell);
        tbody.append(tr);
      }
      table.append(thead, tbody);
      tableArea.append(table);
      const previous = button('Página anterior', () => load(page - 1));
      const next = button('Próxima página', () => load(page + 1));
      previous.disabled = page <= 1;
      next.disabled = page >= (data.total_pages || 1);
      tableArea.append(previous, ' ', next);
    } catch (error) { status.textContent = errorText(error); }
  };
  controls.append(button('Carregar / atualizar registros', () => load(currentPage)));
  if (schema.paths[path].post && allowed(resource, '', 'POST')) {
    controls.append(' ', button(schema.paths[path].post.summary || 'Novo registro', () => {
      detailArea.replaceChildren();
      operationForm(detailArea, schema, 'POST', path, { onSuccess: () => load(1) });
    }));
  }
  const filters = element('details');
  filters.append(element('summary', 'Filtros da consulta'));
  const filterForm = element('form', null, { method: 'post' });
  const inputs = [];
  for (const parameter of listOperation.parameters || []) {
    if (parameter.in !== 'query' || ['page', 'page_size'].includes(parameter.name)) continue;
    const field = resolve(schema, parameter.schema);
    const caption = element('label', `${parameter.name}: `);
    const input = element('input', null, { type: field.type === 'integer' ? 'number' : 'text', name: parameter.name });
    caption.append(input);
    filterForm.append(caption, ' ');
    inputs.push(input);
  }
  filterForm.append(element('button', 'Aplicar filtros', { type: 'submit' }));
  filterForm.addEventListener('submit', event => {
    event.preventDefault();
    const params = new URLSearchParams();
    for (const input of inputs) if (input.value !== '') params.set(input.name, input.value);
    filter = params.size ? `?${params}` : '';
    detailArea.replaceChildren();
    load(1);
  });
  filters.append(filterForm);
  section.append(controls, filters, status, tableArea, detailArea);
  parent.append(section);
}

export function operations(document) {
  return Object.entries(document.paths).flatMap(([path, methods]) =>
    ['get', 'post', 'patch', 'put', 'delete'].filter(method => methods[method])
      .map(method => ({ path, method: method.toUpperCase(), ...methods[method] })));
}

function technicalPanel() {
  workspace.append(element('p', 'O catálogo abaixo é obtido do OpenAPI executável, não de uma cópia antiga. O painel usa a conta real; mostrar uma ação não concede permissão. Toda escrita exige confirmação.'));
  const select = element('select', null, { 'aria-label': 'Operação HTTP' });
  const all = operations(schema);
  for (const [index, operation] of all.entries()) {
    select.append(element('option', `${operation.method} ${operation.path} — ${operation.summary}`, { value: index }));
  }
  const area = element('section');
  const open = () => {
    const operation = all[Number(select.value)];
    area.replaceChildren();
    operationForm(area, schema, operation.method, operation.path, { technical: true });
  };
  workspace.append(element('p', `${all.length} operações HTTP disponíveis no schema atual.`), select,
    button('Abrir formulário técnico', open), area);
  const schemaOutput = element('details');
  schemaOutput.append(element('summary', 'Identificação do contrato carregado'),
    element('pre', JSON.stringify({ openapi: schema.openapi, info: schema.info }, null, 2)));
  workspace.append(schemaOutput);
}

async function main() {
  const response = await fetch('assets/workflows.json', { mode: 'same-origin', credentials: 'same-origin', cache: 'no-store' });
  if (!response.ok) throw new Error('Catálogo local indisponível.');
  const metadata = await response.json();
  schema = (await request('GET', '/api/schema/', { accept: 'application/vnd.oai.openapi+json', refresh: false })).data;
  if (!schema?.paths) throw new Error('Schema JSON indisponível.');
  await updateSession();
  const page = metadata.pages.find(item => item.key === document.body.dataset.page);
  if (!page) throw new Error('Página desconhecida.');
  if (page.key === 'home') login();
  if (page.key === 'panel') technicalPanel();
  for (const resource of page.resources) resourceSection(workspace, resource, metadata);
  for (const operation of page.operations) {
    const [method, path] = operation.split(' ');
    const details = element('details');
    details.append(element('summary', schema.paths[path][method.toLowerCase()].summary || operation));
    let loaded = false;
    details.addEventListener('toggle', () => {
      if (details.open && !loaded) { loaded = true; operationForm(details, schema, method, path); }
    });
    workspace.append(details);
  }
  if (page.key === 'configuration' && role('companies')) habitualSelector(workspace);
  if (page.key === 'location') locationPanel(workspace, { driverId: account?.profiles.drivers?.id });
}

sessionEvents.addEventListener('changed', () => { workspace.replaceChildren(); session.replaceChildren(); location.reload(); });
sessionEvents.addEventListener('refreshed', () => { if (loadedIdentity) updateSession(); });
window.addEventListener('focus', () => { invalidateCsrf(); if (loadedIdentity) updateSession(); });
window.addEventListener('pageshow', event => { if (event.persisted) location.reload(); });
window.addEventListener('pagehide', () => {
  for (const input of document.querySelectorAll('input[type="password"]')) input.value = '';
});
main().catch(error => { workspace.replaceChildren(element('p', errorText(error), { role: 'alert' })); });
