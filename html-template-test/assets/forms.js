import { allRecords, diagnostic, errorText, request } from './client.js';

export function element(tag, text, attributes = {}) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  for (const [name, value] of Object.entries(attributes)) {
    if (value !== undefined && value !== null) node.setAttribute(name, String(value));
  }
  return node;
}

export function button(text, action) {
  const node = element('button', text, { type: 'button' });
  node.addEventListener('click', action);
  return node;
}

export function resolve(document, input = {}) {
  if (input.$ref) {
    if (!input.$ref.startsWith('#/')) throw new Error('Referência externa de schema recusada.');
    const target = input.$ref.slice(2).split('/').reduce((value, key) => value?.[key], document);
    return resolve(document, { ...target, ...Object.fromEntries(Object.entries(input).filter(([key]) => key !== '$ref')) });
  }
  if (input.allOf) return input.allOf.reduce((result, part) => ({ ...result, ...resolve(document, part) }),
    Object.fromEntries(Object.entries(input).filter(([key]) => key !== 'allOf')));
  if (input.oneOf && !input.discriminator) {
    const options = input.oneOf.map(part => resolve(document, part));
    const useful = options.find(part => part.type && part.type !== 'null' && part.maxLength !== 0);
    if (useful) return { ...input, ...useful, nullable: input.nullable || options.some(part => part.type === 'null') };
  }
  return input;
}

const labels = {
  company_id: 'Empresa', route_group_id: 'Grupo de atendimento', transport_point_id: 'Ponto operacional do aluno',
  driver_membership_id: 'Vínculo ativo do motorista', vehicle_id: 'Veículo', destination_id: 'Destino operacional',
  origin_id: 'Origem operacional', garage_point_id: 'Garagem operacional', service_ids: 'Serviços autorizados',
  point_ids: 'Paradas habituais (ordem configurada)', habitual_outbound_id: 'Ida habitual',
  outbound_service_id: 'Ida escolhida', return_service_id: 'Retorno escolhido', proposed_service_id: 'Serviço proposto',
  expected_revision: 'Revisão esperada (lida do servidor)', operation_id: 'Identificador idempotente da operação (UUID)',
  planned_duration: 'Duração planejada (HH:MM:SS)', turnaround_duration: 'Margem entre viagens (HH:MM:SS)',
  name: 'Nome', email: 'E-mail', password: 'Senha', code: 'Código recebido por e-mail', user_data: 'Dados da conta',
  reason: 'Motivo', leg: 'Trecho', kind: 'Evento', travel_id: 'Viagem', target_status: 'Estado de destino',
  corrects_event_id: 'Evento atual a corrigir', next_run_at: 'Próxima execução (ISO 8601 com fuso)',
  weekdays: 'Dias da semana: segunda=1, terça=2, quarta=4, quinta=8, sexta=16, sábado=32, domingo=64; somar',
};

export function label(name, schema = {}) { return labels[name] || schema.title || name; }

export function recordLabel(row) {
  return `${row.name || row.applicant_name || row.trade_name || row.plate || row.user_data?.name || row.date || row.kind || 'Registro'} (#${row.id})`;
}

const relations = {
  company_id: 'companies', route_group_id: 'company-route-groups', driver_membership_id: 'memberships',
  transport_point_id: 'operational-points', vehicle_id: 'vehicles', garage_point_id: 'operational-points',
  origin_id: 'operational-points', destination_id: 'operational-points', point_ids: 'operational-points',
  habitual_outbound_id: 'recurring-services', service_ids: 'recurring-services', travel_id: 'travels',
  corrects_event_id: 'participation-events',
};

async function choices(name, context, readers) {
  if (['outbound_service_id', 'return_service_id', 'proposed_service_id'].includes(name)) {
    const direction = name === 'proposed_service_id' ? readers.leg?.() : name.split('_')[0];
    return (context.authorized_services || []).filter(row => !direction || row.direction === direction)
      .map(row => ({ ...row, name: `${row.name} — ${row.target_time}` }));
  }
  const resource = relations[name];
  if (!resource) return [];
  const url = new URL(`/api/${resource}/`, location.origin);
  if (resource === 'recurring-services') {
    const group = readers.route_group_id ? readers.route_group_id() : context.route_group;
    if (!group) throw new Error('Escolha o grupo antes de carregar serviços.');
    url.searchParams.set('route_group', group);
  }
  if (name === 'habitual_outbound_id') url.searchParams.set('direction', 'outbound');
  if (name === 'driver_membership_id') url.searchParams.set('status', 'active');
  if (name === 'corrects_event_id' && context.id) url.searchParams.set('participation', context.id);
  const rows = await allRecords(url.href);
  return name === 'driver_membership_id' ? rows.filter(row => row.driver !== null) : rows;
}

function primitive(schema, name, seed) {
  let control;
  if (schema.enum || schema.type === 'boolean') {
    control = element('select', null);
    control.append(element('option', 'Selecione', { value: '' }));
    for (const value of schema.enum || [true, false]) {
      control.append(element('option', String(value), { value: String(value) }));
    }
  } else if (schema.type === 'array' || schema.type === 'object') {
    control = element('textarea', null, { rows: 4, cols: 60 });
  } else {
    let type = ['integer', 'number'].includes(schema.type) ? 'number' : 'text';
    if (schema.format === 'email') type = 'email';
    if (schema.format === 'date') type = 'date';
    if (schema.format === 'time') type = 'time';
    if (/password|^code$/.test(name)) type = 'password';
    if (schema.format === 'binary') type = 'file';
    control = element('input', null, { type, autocomplete: type === 'password' ? 'off' : undefined });
    if (type === 'number') {
      control.step = schema.type === 'integer' ? '1' : 'any';
      if (schema.minimum !== undefined) control.min = schema.minimum;
      if (schema.maximum !== undefined) control.max = Math.min(schema.maximum, Number.MAX_SAFE_INTEGER);
    }
    if (type === 'time') control.step = '1';
    if (schema.maxLength !== undefined) control.maxLength = schema.maxLength;
    if (schema.format === 'uuid') control.placeholder = 'UUID';
    if (schema.format === 'date-time') control.placeholder = 'AAAA-MM-DDTHH:MM:SS-03:00 (fuso explícito)';
  }
  control.setAttribute('aria-label', label(name, schema));
  if (seed !== undefined && seed !== null && schema.format !== 'binary') {
    control.value = typeof seed === 'object' ? JSON.stringify(seed) : String(seed);
  }
  return {
    node: control,
    read() {
      if (schema.format === 'binary') {
        if (!control.files[0]) throw new Error('Selecione um arquivo.');
        return control.files[0];
      }
      const value = control.value;
      if (schema.type === 'boolean') {
        if (!['true', 'false'].includes(value)) throw new Error('Escolha verdadeiro ou falso.');
        return value === 'true';
      }
      if (['integer', 'number'].includes(schema.type)) {
        if (value === '' || !Number.isFinite(Number(value))) throw new Error('Número obrigatório.');
        const result = Number(value);
        if (schema.type === 'integer' && !Number.isSafeInteger(result)) throw new Error('Inteiro inválido.');
        return result;
      }
      if (schema.type === 'array' || schema.type === 'object') {
        const parsed = JSON.parse(value || (schema.type === 'array' ? '[]' : '{}'));
        if (schema.type === 'array' ? !Array.isArray(parsed) : !parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
          throw new Error('Estrutura JSON inválida.');
        }
        return parsed;
      }
      if (schema.format === 'date-time' && (!/(Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value)))) {
        throw new Error('Informe um instante ISO 8601 com fuso explícito.');
      }
      if (schema.enum && !schema.enum.includes(value)) throw new Error('Selecione uma opção válida.');
      return value;
    },
  };
}

function relationField(schema, name, seed, context, readers) {
  const node = element('div');
  const multiple = schema.type === 'array';
  const select = element('select', null, { 'aria-label': label(name, schema) });
  select.append(element('option', 'Selecione um registro', { value: '' }));
  if (!multiple && seed !== undefined && seed !== null) {
    select.append(element('option', `Registro #${seed} (configuração atual)`, { value: seed }));
    select.value = seed;
  }
  let selected = Array.isArray(seed) ? [...seed] : [];
  let rows = [];
  const list = element('ol');
  const options = element('div');
  const output = element('p', '', { role: 'status' });
  const render = () => {
    list.replaceChildren();
    options.replaceChildren();
    for (const [index, id] of selected.entries()) {
      const item = element('li', rows.find(row => row.id === id) ? recordLabel(rows.find(row => row.id === id)) : `Registro #${id}`);
      item.append(' ', button('Retirar', () => { selected = selected.filter(value => value !== id); render(); }));
      if (name === 'point_ids') {
        item.append(' ', button('Subir', () => {
          if (index > 0) { [selected[index - 1], selected[index]] = [selected[index], selected[index - 1]]; render(); }
        }), ' ', button('Descer', () => {
          if (index < selected.length - 1) { [selected[index + 1], selected[index]] = [selected[index], selected[index + 1]]; render(); }
        }));
      }
      list.append(item);
    }
    for (const row of rows) {
      const line = element('p');
      const caption = element('label');
      const checkbox = element('input', null, { type: 'checkbox' });
      checkbox.checked = selected.includes(row.id);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked && !selected.includes(row.id)) selected.push(row.id);
        if (!checkbox.checked) selected = selected.filter(value => value !== row.id);
        render();
      });
      caption.append(checkbox, ' ', recordLabel(row));
      line.append(caption);
      options.append(line);
    }
  };
  const load = button('Carregar opções autorizadas', async () => {
    load.disabled = true;
    try {
      rows = await choices(name, context, readers);
      if (multiple) render();
      else {
        const previous = select.value;
        select.replaceChildren(element('option', 'Selecione um registro', { value: '' }));
        for (const row of rows) select.append(element('option', recordLabel(row), { value: row.id }));
        if (previous && !rows.some(row => String(row.id) === previous)) {
          select.append(element('option', `Registro #${previous} (revalidar acesso)`, { value: previous }));
        }
        select.value = previous;
      }
      output.textContent = `${rows.length} opções autorizadas. Nenhuma seleção foi feita automaticamente.`;
    } catch (error) { output.textContent = errorText(error); }
    finally { load.disabled = false; }
  });
  node.append(multiple ? list : select, load, output);
  if (multiple) { node.append(options); render(); }
  return {
    node,
    read() {
      if (multiple) return [...selected];
      if (!select.value) throw new Error('Selecione um registro autorizado.');
      return schema.type === 'integer' ? Number(select.value) : select.value;
    },
  };
}

function objectFields(document, source, seed = {}, context = {}, technical = false) {
  const schema = resolve(document, source);
  const node = element('div');
  if (schema.discriminator) {
    const selector = element('select', null, { 'aria-label': 'Tipo de cadastro', required: '' });
    selector.append(element('option', 'Escolha o tipo de cadastro', { value: '' }));
    const content = element('div');
    let branch;
    for (const name of Object.keys(schema.discriminator.mapping)) selector.append(element('option', name, { value: name }));
    selector.addEventListener('change', () => {
      const reference = schema.discriminator.mapping[selector.value];
      content.replaceChildren();
      branch = reference ? objectFields(document, { $ref: reference }, {}, context, technical) : null;
      if (branch) content.append(branch.node);
    });
    node.append(element('p', 'Tipo de cadastro'), selector, content);
    return { node, read: () => {
      if (!branch) throw new Error('Escolha o tipo de cadastro.');
      return { ...branch.read(), [schema.discriminator.propertyName]: selector.value };
    } };
  }
  const readers = {};
  for (const [name, input] of Object.entries(schema.properties || {})) {
    const field = resolve(document, input);
    if (field.readOnly) continue;
    const required = (schema.required || []).includes(name);
    const wrapper = element('fieldset');
    wrapper.append(element('legend', `${label(name, field)}${required ? ' (obrigatório)' : ''}`));
    const mode = element('select', null, { 'aria-label': `Como enviar ${label(name, field)}` });
    if (!required) mode.append(element('option', 'Não enviar este campo', { value: 'omit' }));
    mode.append(element('option', 'Enviar valor', { value: 'value' }));
    if (field.nullable) mode.append(element('option', 'Enviar nulo explicitamente', { value: 'null' }));
    if (seed[name] === null && field.nullable) mode.value = 'null';
    else if (seed[name] !== undefined || required) mode.value = 'value';
    const content = element('fieldset');
    let value = seed[name];
    if (name === 'operation_id' && value === undefined) value = crypto.randomUUID();
    const control = field.type === 'object' && field.properties
      ? objectFields(document, field, value || {}, context, technical)
      : !technical && (relations[name] || ['outbound_service_id', 'return_service_id', 'proposed_service_id'].includes(name))
        ? relationField(field, name, value, context, readers) : primitive(field, name, value);
    if (field.description) wrapper.append(element('p', field.description));
    content.append(control.node);
    wrapper.append(mode, content);
    const toggle = () => { content.disabled = mode.value !== 'value'; };
    mode.addEventListener('change', toggle);
    toggle();
    if (name === 'operation_id') content.append(button('Novo UUID (nova operação, não retry)', () => {
      if (confirm('Trocar o UUID cria uma nova operação. Não use após falha de rede com resultado desconhecido. Continuar?')) {
        control.node.value = crypto.randomUUID();
      }
    }));
    readers[name] = () => {
      if (mode.value === 'omit') return undefined;
      if (mode.value === 'null') return null;
      return control.read();
    };
    node.append(wrapper);
  }
  return { node, read: () => Object.fromEntries(Object.entries(readers)
    .map(([name, read]) => [name, read()]).filter(([, value]) => value !== undefined)) };
}

export function showData(parent, data) {
  parent.replaceChildren();
  if (data instanceof Blob) {
    parent.append(button('Baixar arquivo autorizado', () => {
      const url = URL.createObjectURL(data);
      const link = element('a', 'Download', { href: url, download: 'documento.pdf' });
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }));
  } else {
    const details = element('details');
    details.append(element('summary', 'Dados retornados para esta conta (somente nesta página)'),
      element('pre', JSON.stringify(data, null, 2)));
    parent.append(details);
  }
}

export function operationForm(parent, document, method, path, options = {}) {
  const operation = document.paths[path]?.[method.toLowerCase()];
  if (!operation) throw new Error('Operação ausente do OpenAPI atual.');
  const form = element('form', null, { method: 'post' });
  form.append(element('h3', operation.summary || `${method} ${path}`));
  const endpoint = element('details');
  endpoint.append(element('summary', 'Contrato HTTP'), element('code', `${method} ${path}`), element('p', operation.description || ''));
  form.append(endpoint);
  const schema = { type: 'object', properties: {}, required: [] };
  for (const parameter of operation.parameters || []) {
    if (parameter.in === 'path' || (parameter.in === 'query' && (method === 'GET' || options.technical))) {
      const name = `${parameter.in}__${parameter.name}`;
      schema.properties[name] = { ...resolve(document, parameter.schema), title: `${parameter.name} (${parameter.in})` };
      if (parameter.required) schema.required.push(name);
    }
  }
  if (path === '/api/companies/me/stats/') schema.properties.query__date = { type: 'string', format: 'date', title: 'Data de atendimento' };
  const parameterSeed = {};
  for (const [name, value] of Object.entries(options.params || {})) parameterSeed[`path__${name}`] = value;
  const parameters = objectFields(document, schema, parameterSeed, {}, true);
  form.append(parameters.node);
  const formats = operation.requestBody?.content || {};
  const format = formats['application/json'] ? 'application/json' : formats['multipart/form-data'] ? 'multipart/form-data' : null;
  const fields = format ? objectFields(document, formats[format].schema, options.seed || {}, options.context || {}, options.technical) : null;
  if (fields) form.append(fields.node);
  const submit = element('button', method === 'GET' ? 'Consultar' : 'Confirmar operação', { type: 'submit' });
  const status = element('p', '', { role: 'status' });
  const result = element('div');
  const diagnosticDetails = element('details');
  const diagnosticOutput = element('pre');
  diagnosticDetails.append(element('summary', 'Diagnóstico sem valores sensíveis'), diagnosticOutput);
  form.append(submit, status, result, diagnosticDetails);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    submit.disabled = true;
    let success = false;
    try {
      const values = parameters.read();
      let target = path.replace(/\{([^}]+)\}/g, (_, name) => {
        const value = values[`path__${name}`];
        if (value === undefined || value === '') throw new Error('Identificador obrigatório.');
        return encodeURIComponent(value);
      });
      const url = new URL(target, location.origin);
      for (const [name, value] of Object.entries(values)) {
        if (name.startsWith('query__')) url.searchParams.set(name.slice(7), value);
      }
      let body = fields?.read();
      if (format === 'multipart/form-data') {
        const multipart = new FormData();
        for (const [name, value] of Object.entries(body)) multipart.append(name, value);
        body = multipart;
      }
      if (method !== 'GET' && !confirm('Executar esta operação real na API? Confira a conta, o recurso e os campos.')) return;
      status.textContent = 'Enviando…';
      const response = await request(method, url.href, { body });
      success = true;
      status.textContent = `HTTP ${response.status}. ${method === 'GET' ? 'Consulta concluída.' : 'Operação concluída. Abra a ação novamente para uma nova operação.'}`;
      showData(result, response.data);
      diagnosticOutput.textContent = JSON.stringify({ method, endpoint: path, status: response.status, response: diagnostic(response.data) }, null, 2);
      await options.onSuccess?.(response.data);
    } catch (error) {
      status.textContent = errorText(error) + (error.uncertain ? ' Não altere o UUID nem repita sem verificar o resultado.' : '');
      result.replaceChildren();
      if (error.status === 400 && error.data) {
        result.append(element('p', 'Validação retornada pela API (não registrada em log):'),
          element('pre', JSON.stringify(error.data, (key, value) => /password|code|token|cpf|cnpj/i.test(key) ? '[campo sensível]' : value, 2)));
      }
      diagnosticOutput.textContent = JSON.stringify({ method, endpoint: path, status: error.status || 0, response: diagnostic(error.data) }, null, 2);
    } finally { submit.disabled = success && method !== 'GET'; }
  });
  parent.append(form);
  return form;
}
