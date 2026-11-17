// Sessão apenas em cookies HttpOnly. Nenhum dado é persistido pelo cliente.
let csrfToken = null;
let csrfPending = null;
let refreshing = null;
export const sessionEvents = new EventTarget();
const channel = typeof BroadcastChannel === 'function'
  ? new BroadcastChannel('nextrouter-html-session') : null;

function signal(kind, broadcast = true) {
  csrfToken = null;
  sessionEvents.dispatchEvent(new Event(kind));
  if (broadcast) channel?.postMessage(kind);
}

if (channel) channel.onmessage = ({ data }) => {
  if (data === 'changed' || data === 'refreshed') signal(data, false);
};

export class ApiError extends Error {
  constructor(status, data, uncertain = false) {
    super(status ? `HTTP ${status}` : 'Falha de rede. O resultado pode ser desconhecido.');
    this.status = status;
    this.data = data;
    this.uncertain = uncertain;
  }
}

export function apiUrl(path) {
  const url = new URL(path, globalThis.location.origin);
  if (url.origin !== globalThis.location.origin || !url.pathname.startsWith('/api/') || url.hash
      || url.username || url.password) throw new Error('Somente URLs /api/ da mesma origem são aceitas.');
  return url;
}

async function raw(method, path, { body, accept = 'application/json' } = {}) {
  const headers = { Accept: accept };
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers['X-CSRFToken'] = await csrf();
  const options = {
    method, headers, mode: 'same-origin', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
  };
  if (body !== undefined) {
    if (body instanceof FormData) options.body = body;
    else {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
  }
  let response;
  try { response = await fetch(apiUrl(path), options); }
  catch { throw new ApiError(0, null, !['GET', 'HEAD'].includes(method)); }
  const type = response.headers.get('content-type') || '';
  let data = null;
  if (method === 'HEAD' || response.status === 204) {
    data = null;
  } else if (type.includes('json')) {
    try { data = await response.json(); } catch { throw new ApiError(response.status, null, true); }
  } else if (type.startsWith('text/')) {
    // Não reproduzir páginas de erro DEBUG/tracebacks no diagnóstico.
    data = { detail: 'Resposta não JSON. Confira a URL, o servidor e o schema.' };
  } else if (response.ok && method !== 'HEAD' && response.status !== 204) data = await response.blob();
  if (!response.ok) throw new ApiError(response.status, data);
  return { data, status: response.status, headers: response.headers };
}

export async function csrf() {
  if (csrfPending) return csrfPending;
  if (!csrfToken) {
    csrfPending = raw('GET', '/api/csrf/').then(({ data }) => {
      if (!data?.csrfToken) throw new Error('Bootstrap CSRF inválido.');
      csrfToken = data.csrfToken;
      return csrfToken;
    }).finally(() => { csrfPending = null; });
    return csrfPending;
  }
  return csrfToken;
}

export async function refreshSession({ manual = false, path = '/api/refresh/' } = {}) {
  if (!['/api/refresh/', '/api/token/refresh/'].includes(path)) throw new Error('Endpoint de renovação inválido.');
  if (refreshing) return refreshing;
  if (!globalThis.navigator?.locks && !manual) {
    throw new Error('Este navegador exige renovação manual da sessão; use Renovar sessão em uma única aba.');
  }
  const refresh = async () => {
    // Outra aba pode ter renovado enquanto aguardávamos o lock.
    if (!manual) {
      try { await raw('GET', '/api/users/me/'); return; }
      catch (error) { if (error.status !== 401) throw error; }
    }
    csrfToken = null;
    const result = await raw('POST', path);
    signal('refreshed');
    return result;
  };
  refreshing = (globalThis.navigator?.locks
    ? navigator.locks.request('nextrouter-cookie-refresh', refresh) : refresh()).finally(() => { refreshing = null; });
  return refreshing;
}

export async function request(method, path, options = {}) {
  method = method.toUpperCase();
  const pathname = apiUrl(path).pathname;
  if (method === 'POST' && ['/api/refresh/', '/api/token/refresh/'].includes(pathname)) {
    if (options.body !== undefined) throw new Error('A renovação não aceita corpo de requisição.');
    return refreshSession({ manual: true, path: pathname });
  }
  let result;
  try { result = await raw(method, path, options); }
  catch (error) {
    // Nunca repetir mutações; 403 não é motivo para renovar.
    if (error.status !== 401 || method !== 'GET' || options.refresh === false) throw error;
    await refreshSession();
    result = await raw(method, path, options);
  }
  if (['/api/login/', '/api/token/'].includes(pathname) && method === 'POST') {
    signal('changed');
    csrfToken = result.data.csrfToken;
  } else if (['/api/me/logout/', '/api/token/logout/', '/api/me/revoke-sessions/', '/api/me/deactivate/']
      .includes(pathname) && method === 'POST') signal('changed');
  return result;
}

export async function collection(path, page = 1) {
  const url = apiUrl(path);
  url.searchParams.set('page', page);
  url.searchParams.set('page_size', '25');
  const { data } = await request('GET', url.href);
  return Array.isArray(data) ? { results: data, total_pages: 1 } : data;
}

export async function allRecords(path) {
  const records = [];
  let page = 1;
  let data;
  do {
    data = await collection(path, page++);
    if (!Array.isArray(data?.results)) throw new Error('Resposta de lista inválida.');
    records.push(...data.results);
  } while (page <= data.total_pages);
  return records;
}

export async function identity() {
  const { data: user } = await request('GET', '/api/users/me/');
  const profiles = {};
  for (const resource of ['companies', 'drivers', 'passengers']) {
    try { profiles[resource] = (await request('GET', `/api/${resource}/me/`)).data; }
    catch (error) { if (![403, 404].includes(error.status)) throw error; }
  }
  return { user, profiles };
}

export function invalidateCsrf() { csrfToken = null; }

// Diagnósticos são efêmeros e por allowlist; valores livres/PII/segredos não são logs.
export function diagnostic(value, key = '') {
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) return value.map(item => diagnostic(item, key));
  if (typeof value === 'object') return Object.fromEntries(
    Object.entries(value).map(([name, item]) => [name, diagnostic(item, name)])
  );
  return /^(id|.*_id|revision|expected_revision|status|state|planning_status|code|count|total_pages|page|partial|stale|current|application|attempts|enabled|score)$/.test(key)
    ? value : '[omitido do diagnóstico]';
}

export function errorText(error) {
  const prefix = error.status ? `HTTP ${error.status}. ` : '';
  const notices = {
    401: 'Sessão ausente ou expirada. Renove a sessão ou entre novamente; a operação não foi repetida.',
    403: 'Acesso ou CSRF recusado. Atualize a sessão; não haverá refresh automático por este erro.',
    404: 'Recurso inexistente ou não autorizado para esta conta.',
    409: 'Conflito de revisão, capacidade, idempotência ou estado. Releia o recurso antes de decidir novamente.',
    429: 'Limite de requisições atingido. Aguarde antes de tentar novamente.',
  };
  if (notices[error.status]) return prefix + notices[error.status];
  if (error.status === 400) return prefix + 'Dados ou janela operacional inválidos. Confira os campos e os prazos.';
  return prefix + (error instanceof ApiError ? error.message : 'Não foi possível concluir. Confira os campos e a conexão.');
}
