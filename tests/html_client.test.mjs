import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { stopChild } from '../scripts/test_html_browser.mjs';

// Sem navegador, bibliotecas DOM, npm ou rede. Somente fixtures em memória.
globalThis.location = new URL('http://localhost:8000');
globalThis.BroadcastChannel = undefined;
Object.defineProperty(globalThis, 'navigator', { value: { locks: { request: async (_, callback) => callback() } }, configurable: true });
const client = await import('../html-template-test/assets/client.js');
const { resolve } = await import('../html-template-test/assets/forms.js');
const { authorizationChange } = await import('../html-template-test/assets/habitual.js');
const { socketUrl } = await import('../html-template-test/assets/location.js');

const json = (status, data) => new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json' } });
let calls;
function mock(handler) {
  calls = [];
  client.invalidateCsrf();
  globalThis.fetch = async (url, options) => {
    const path = new URL(url).pathname;
    calls.push({ path, url: String(url), ...options });
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.mode, 'same-origin');
    assert.equal(options.redirect, 'error');
    assert.equal(options.headers.Authorization, undefined);
    if (path === '/api/csrf/') return json(200, { csrfToken: 'csrf-fixture' });
    return handler(path, options);
  };
}

test('bloqueia outras origens e prefixos, inclusive URLs protocol-relative', () => {
  for (const path of ['https://other.invalid/api/travels/', '//other.invalid/api/', '/admin/', '/api/travels/#secret']) {
    assert.throws(() => client.apiUrl(path));
  }
  assert.equal(client.apiUrl('/api/travels/?page=2').origin, location.origin);
});

test('CSRF compartilhado entre requisições e rotacionado no login; sem JWT no cliente', async () => {
  mock((path, options) => {
    if (path === '/api/login/') {
      assert.equal(options.headers['X-CSRFToken'], 'csrf-fixture');
      return json(200, { detail: 'Sessão iniciada.', csrfToken: 'csrf-rotated' });
    }
    assert.equal(options.headers['X-CSRFToken'], 'csrf-rotated');
    return json(200, {});
  });
  await Promise.all([client.csrf(), client.csrf()]);
  assert.equal(calls.filter(item => item.path === '/api/csrf/').length, 1);
  await client.request('POST', '/api/login/', { body: { email: 'fixture@example.invalid', password: 'fictitious' } });
  await client.request('POST', '/api/notifications/1/read/');
});

test('coleções usam paginação real e preservam filtros', async () => {
  mock(() => json(200, { results: [{ id: 1 }], total_pages: 1 }));
  assert.deepEqual(await client.allRecords('/api/company-route-groups/?company=4'), [{ id: 1 }]);
  const url = new URL(calls[0].url);
  assert.equal(url.searchParams.get('company'), '4');
  assert.equal(url.searchParams.get('page'), '1');
  assert.equal(url.searchParams.get('page_size'), '25');
});

test('GET pode renovar uma única vez, sem corpo no refresh e sem tocar cookies por JS', async () => {
  let valid = false;
  mock((path, options) => {
    if (path === '/api/refresh/') {
      assert.equal(options.method, 'POST');
      assert.equal(options.body, undefined);
      valid = true;
      return json(200, { detail: 'Sessão renovada.' });
    }
    return valid ? json(200, { id: 1 }) : json(401, { detail: 'Expirado' });
  });
  assert.equal((await client.request('GET', '/api/travels/')).data.id, 1);
  assert.equal(calls.filter(item => item.path === '/api/refresh/').length, 1);
  assert.equal(calls.filter(item => item.path === '/api/travels/').length, 2);
});

test('401 de mutação nunca provoca refresh nem replay; 403 de GET também não', async () => {
  mock(() => json(401, { detail: 'Expirado' }));
  await assert.rejects(client.request('POST', '/api/travels/1/start/', { body: { expected_revision: 1 } }), { status: 401 });
  assert.equal(calls.filter(item => item.path.includes('/start/')).length, 1);
  assert.equal(calls.filter(item => item.path === '/api/refresh/').length, 0);
  mock(() => json(403, { detail: 'Recusado' }));
  await assert.rejects(client.request('GET', '/api/travels/'), { status: 403 });
  assert.equal(calls.length, 1);
});

test('segundo 401 encerra a tentativa; falha de rede de mutação conserva resultado incerto', async () => {
  mock(path => path === '/api/refresh/' ? json(200, {}) : json(401, {}));
  await assert.rejects(client.request('GET', '/api/travels/'), { status: 401 });
  assert.equal(calls.filter(item => item.path === '/api/refresh/').length, 1);
  mock(() => { throw new Error('network fixture'); });
  await assert.rejects(client.request('POST', '/api/travel-participations/1/record/', { body: { operation_id: 'fixed' } }), { uncertain: true });
  assert.equal(calls.filter(item => item.path.includes('/record/')).length, 1);
});

test('single-flight de renovação e coordenação por lock', async () => {
  let rotations = 0;
  mock(path => {
    if (path === '/api/refresh/') { rotations++; return json(200, {}); }
    return json(401, {});
  });
  await Promise.all([client.refreshSession(), client.refreshSession(), client.refreshSession()]);
  assert.equal(rotations, 1);
  const previous = navigator.locks;
  navigator.locks = null;
  await assert.rejects(client.refreshSession(), /renovação manual/);
  navigator.locks = previous;
});

test('refresh no painel e seu alias usam a mesma coordenação e avisam sockets/abas', async () => {
  let events = 0;
  const listener = () => events++;
  client.sessionEvents.addEventListener('refreshed', listener);
  mock((path, options) => {
    assert.equal(path, '/api/token/refresh/');
    assert.equal(options.body, undefined);
    return json(200, { detail: 'Renovada' });
  });
  const results = await Promise.all([
    client.request('POST', '/api/token/refresh/'), client.request('POST', '/api/token/refresh/'),
  ]);
  assert.equal(calls.filter(item => item.path === '/api/token/refresh/').length, 1);
  assert.equal(events, 1);
  assert.equal(results[0].status, 200);
  await assert.rejects(client.request('POST', '/api/refresh/', { body: { refresh: 'never-send-jwt' } }));
  client.sessionEvents.removeEventListener('refreshed', listener);
});

test('HEAD e 204 não tentam interpretar JSON vazio; erros HTML não vazam traceback', async () => {
  mock(() => new Response(null, { status: 204 }));
  assert.equal((await client.request('POST', '/api/me/logout/')).data, null);
  mock(() => new Response(null, { status: 200, headers: { 'content-type': 'application/json' } }));
  assert.equal((await client.request('HEAD', '/api/users/me/')).data, null);
  mock(() => new Response('FIXTURE_TRACEBACK_PRIVATE', { status: 500, headers: { 'content-type': 'text/html' } }));
  try { await client.request('GET', '/api/travels/'); assert.fail('Deveria falhar'); }
  catch (error) { assert.ok(!JSON.stringify(error.data).includes('FIXTURE_TRACEBACK_PRIVATE')); }
});

test('diagnóstico oculta valores livres, identidade, códigos e coordenadas', () => {
  const result = client.diagnostic({ id: 1, status: 'ready', password: 'SECRET', csrfToken: 'SECRET',
    user_data: { name: 'SECRET', cpf: 'SECRET' }, point_snapshot: { street: 'SECRET', latitude: 12.3 },
    geometry: { coordinates: [[12.3, 45.6]] }, detail: 'SECRET' });
  const output = JSON.stringify(result);
  assert.ok(!output.includes('SECRET'));
  assert.ok(!output.includes('12.3'));
  assert.equal(result.id, 1);
  assert.equal(result.status, 'ready');
});

test('seleção habitual preserva retornos e outras autorizações; retirar habitual não retira autorização', () => {
  const member = { service_ids: [1, 2, 3], habitual_outbound_id: 1 };
  assert.deepEqual(authorizationChange(member, { id: 4, direction: 'outbound' }, true),
    { service_ids: [1, 2, 3, 4], habitual_outbound_id: 4 });
  assert.deepEqual(authorizationChange(member, { id: 1, direction: 'outbound' }, false),
    { service_ids: [1, 2, 3], habitual_outbound_id: null });
  assert.deepEqual(authorizationChange(member, { id: 2, direction: 'return' }, false),
    { service_ids: [1, 3], habitual_outbound_id: 1 });
  assert.deepEqual(member, { service_ids: [1, 2, 3], habitual_outbound_id: 1 });
});

test('resolve referências/allOf de campos e deriva WS/WSS da origem sem tokens', () => {
  const document = { components: { schemas: { Direction: { type: 'string', enum: ['outbound', 'return'] } } } };
  assert.deepEqual(resolve(document, { allOf: [{ $ref: '#/components/schemas/Direction' }], title: 'Sentido' }).enum, ['outbound', 'return']);
  assert.throws(() => resolve(document, { $ref: 'https://other.invalid/schema' }));
  assert.equal(socketUrl(1), 'ws://localhost:8000/ws/travels/1/location/');
  globalThis.location = new URL('https://localhost:8443');
  assert.equal(socketUrl(2), 'wss://localhost:8443/ws/travels/2/location/');
  assert.throws(() => socketUrl('1?token=bad'));
  globalThis.location = new URL('http://localhost:8000');
});

test('smoke HTML recusa preparar recursos sem confirmação fictícia', () => {
  const result = spawnSync(process.execPath, [fileURLToPath(new URL('../scripts/test_html_browser.mjs', import.meta.url))], {
    encoding: 'utf8', timeout: 10000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Exige --confirm-fictitious/);
});

test('smoke encerra filhos mortos por sinal sem aguardar um segundo evento exit', async () => {
  const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'ignore' });
  await once(child, 'spawn');
  await stopChild(child, 100);
  assert.equal(child.exitCode, null);
  assert.equal(child.signalCode, 'SIGTERM');
  await stopChild(child, 100);
});
