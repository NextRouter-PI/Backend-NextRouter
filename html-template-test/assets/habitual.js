import { allRecords, errorText, request } from './client.js';
import { button, element, recordLabel } from './forms.js';

export function authorizationChange(member, service, selected) {
  const ids = new Set(member.service_ids);
  let habitual = member.habitual_outbound_id;
  if (service.direction === 'outbound') {
    if (selected) { ids.add(service.id); habitual = service.id; }
    else if (habitual === service.id) habitual = null;
  } else {
    if (selected) ids.add(service.id);
    else ids.delete(service.id);
  }
  return { service_ids: [...ids], habitual_outbound_id: habitual };
}

function unchanged(before, after) {
  return before.habitual_outbound_id === after.habitual_outbound_id
    && JSON.stringify([...before.service_ids].sort((a, b) => a - b)) === JSON.stringify([...after.service_ids].sort((a, b) => a - b));
}

export function habitualSelector(parent) {
  const section = element('section');
  section.append(element('h2', 'Selecionar alunos de um serviço habitual — escolha manual'),
    element('p', 'Mapa adiado. Na ida, marcar define a ida habitual e preserva outras autorizações; desmarcar apenas retira o caráter habitual, sem retirar a autorização. No retorno, marcar/desmarcar autoriza/retira somente aquele retorno. Grupo e ponto não são trocados por esta tela.'),
    element('p', 'Cada aluno é salvo por uma requisição separada: não há transação coletiva. Alterações concorrentes detectadas antes do envio são recusadas; a API atual não oferece revisão otimista desta configuração.'));
  const group = element('select', null, { 'aria-label': 'Grupo de atendimento' });
  const service = element('select', null, { 'aria-label': 'Serviço habitual' });
  const status = element('p', '', { role: 'status' });
  const list = element('div');
  const results = element('ul');
  let services = [];
  let members = [];
  let controls = [];
  let selectionKey = '';
  const reset = () => { list.replaceChildren(); results.replaceChildren(); controls = []; members = []; selectionKey = ''; };
  group.addEventListener('change', () => { reset(); service.replaceChildren(); services = []; });
  service.addEventListener('change', reset);
  const groups = button('Carregar grupos', async () => {
    reset();
    try {
      const rows = await allRecords('/api/company-route-groups/');
      group.replaceChildren(element('option', 'Selecione um grupo', { value: '' }));
      for (const row of rows) group.append(element('option', recordLabel(row), { value: row.id }));
      service.replaceChildren();
    } catch (error) { status.textContent = errorText(error); }
  });
  const loadServices = button('Carregar serviços do grupo', async () => {
    reset();
    try {
      if (!group.value) throw new Error('Escolha um grupo.');
      services = await allRecords(`/api/recurring-services/?route_group=${encodeURIComponent(group.value)}`);
      service.replaceChildren(element('option', 'Selecione um serviço', { value: '' }));
      for (const row of services) service.append(element('option', `${recordLabel(row)} — ${row.direction}`, { value: row.id }));
    } catch (error) { status.textContent = errorText(error); }
  });
  const loadMembers = button('Carregar alunos e seleção atual', async () => {
    reset();
    try {
      const selectedService = services.find(row => String(row.id) === service.value);
      if (!selectedService || String(selectedService.route_group) !== group.value) throw new Error('Escolha grupo e serviço.');
      members = (await allRecords(`/api/group-memberships/?route_group=${encodeURIComponent(group.value)}`))
        .filter(member => !member.ended_at);
      const memberships = await allRecords('/api/memberships/?status=active');
      selectionKey = `${group.value}:${service.value}`;
      for (const member of members) {
        const name = memberships.find(row => row.id === member.membership)?.applicant_name || `Aluno do vínculo #${member.membership}`;
        const checkbox = element('input', null, { type: 'checkbox' });
        checkbox.checked = selectedService.direction === 'outbound'
          ? member.habitual_outbound_id === selectedService.id : member.service_ids.includes(selectedService.id);
        const initial = checkbox.checked;
        const caption = element('label');
        caption.append(checkbox, ` ${name} — ponto operacional #${member.transport_point ?? 'não configurado'}`);
        const line = element('p');
        line.append(caption);
        list.append(line);
        controls.push({ member, checkbox, initial });
      }
      status.textContent = `${members.length} alunos carregados. Nenhuma atribuição foi calculada automaticamente.`;
    } catch (error) { status.textContent = errorText(error); }
  });
  const save = button('Salvar somente alterações selecionadas', async () => {
    const editable = [...section.querySelectorAll('button, input, select')];
    for (const control of editable) control.disabled = true;
    results.replaceChildren();
    try {
      const selectedService = services.find(row => String(row.id) === service.value);
      if (!selectionKey || selectionKey !== `${group.value}:${service.value}` || !selectedService) throw new Error('Recarregue a seleção.');
      const changes = controls.filter(control => control.checkbox.checked !== control.initial)
        .map(control => ({ control, selected: control.checkbox.checked }));
      if (!changes.length) { status.textContent = 'Nenhuma alteração.'; return; }
      if (!confirm(`Salvar ${changes.length} alterações reais, individualmente, preservando as demais autorizações?`)) return;
      for (const { control, selected } of changes) {
        try {
          const { data: current } = await request('GET', `/api/group-memberships/${control.member.id}/`);
          if (!unchanged(control.member, current) || current.ended_at) {
            results.append(element('li', `Participação #${control.member.id}: configuração mudou; nada foi enviado. Recarregue.`));
            continue;
          }
          const body = authorizationChange(current, selectedService, selected);
          const { data } = await request('POST', `/api/group-memberships/${current.id}/authorize-services/`, { body });
          control.member = data;
          control.initial = selected;
          results.append(element('li', `Participação #${current.id}: salva.`));
        } catch (error) {
          results.append(element('li', `Participação #${control.member.id}: ${errorText(error)} Verifique o estado antes de reenviar.`));
          if ([0, 401, 403].includes(error.status)) break;
        }
      }
      status.textContent = 'Processamento encerrado. Confira cada resultado; falhas não desfazem os outros alunos.';
    } catch (error) { status.textContent = errorText(error); }
    finally { for (const control of editable) control.disabled = false; }
  });
  section.append(groups, ' ', group, ' ', loadServices, ' ', service, ' ', loadMembers, status, list, save, results);
  parent.append(section);
}
