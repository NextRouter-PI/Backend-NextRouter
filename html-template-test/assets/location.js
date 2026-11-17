import { allRecords, errorText, request, sessionEvents } from './client.js';
import { button, element, recordLabel } from './forms.js';

export function socketUrl(travelId) {
  if (!/^[1-9]\d*$/.test(String(travelId))) throw new Error('Viagem inválida.');
  return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/travels/${travelId}/location/`;
}

export function locationPanel(parent, { driverId } = {}) {
  const section = element('section');
  section.append(element('h2', 'Acompanhar uma viagem em andamento'),
    element('p', 'Somente viagens autorizadas. O motorista designado pode enviar; empresa e aluno autorizado recebem. Sem JWT na URL, mapa, envio periódico ou GPS em segundo plano. GPS não comprova embarque.'),
    element('p', 'A cadência e a idade dos pontos são validadas pelo servidor. Não envie repetidamente; relógio adiantado, posição futura, fora de ordem ou muito antiga podem ser recusados.'));
  const travel = element('select', null, { 'aria-label': 'Viagem em andamento' });
  const status = element('p', 'Desconectado.', { role: 'status' });
  const position = element('output', 'Sem posição consultada.');
  const lastUpdate = element('p');
  const sender = element('fieldset');
  sender.append(element('legend', 'Motorista designado — envio explícito'));
  sender.disabled = true;
  const latitude = element('input', null, { type: 'number', step: 'any', min: -90, max: 90, required: '', 'aria-label': 'Latitude' });
  const longitude = element('input', null, { type: 'number', step: 'any', min: -180, max: 180, required: '', 'aria-label': 'Longitude' });
  const latitudeLabel = element('label', 'Latitude: ');
  const longitudeLabel = element('label', 'Longitude: ');
  latitudeLabel.append(latitude);
  longitudeLabel.append(longitude);
  sender.append(latitudeLabel, ' ', longitudeLabel);
  const sendForm = element('form', null, { method: 'post' });
  sendForm.append(sender);
  let rows = [];
  let socket = null;
  let wanted = false;
  let waiting = false;

  const clearPosition = () => { position.textContent = 'Sem posição disponível.'; lastUpdate.textContent = ''; };
  const showPosition = data => {
    if (!data.position) { clearPosition(); lastUpdate.textContent = 'Servidor informa posição ausente.'; return; }
    position.textContent = `${data.position.latitude}, ${data.position.longitude}`;
    lastUpdate.textContent = `Atualização: ${data.position.updated_at}. ${data.stale ? 'DESATUALIZADA — não é posição atual.' : 'Dentro da validade informada pelo servidor.'}`;
  };
  const close = (forget = true) => {
    if (forget) wanted = false;
    const previous = socket;
    socket = null;
    previous?.close(1000);
    sender.disabled = true;
    clearPosition();
  };
  const connect = () => {
    if (!travel.value) { status.textContent = 'Escolha uma viagem.'; return; }
    close(false);
    wanted = true;
    const connection = new WebSocket(socketUrl(travel.value));
    socket = connection;
    status.textContent = 'Conectando…';
    connection.onopen = () => {
      if (socket !== connection) return;
      status.textContent = 'Conectado; aguardando dados autorizados do servidor.';
      sender.disabled = !driverId || rows.find(row => String(row.id) === travel.value)?.driver !== driverId;
    };
    connection.onmessage = event => {
      if (socket !== connection) return;
      let data;
      try { data = JSON.parse(event.data); }
      catch { status.textContent = 'Mensagem incompatível; conexão encerrada.'; close(); return; }
      if (data.type === 'location') showPosition(data);
      if (data.type === 'error') status.textContent = 'Posição recusada pelo servidor. Confira horário, coordenadas e intervalo.';
      if (data.type === 'closed') { status.textContent = 'Viagem encerrada.'; close(); }
    };
    connection.onerror = () => {
      if (socket === connection) status.textContent = 'Não foi possível manter o canal. Verifique sessão, origem e servidor.';
    };
    connection.onclose = event => {
      if (socket !== connection) return;
      socket = null;
      sender.disabled = true;
      clearPosition();
      if ([4003, 4009].includes(event.code)) wanted = false;
      status.textContent = `Canal fechado (${event.code}). ${event.code === 4001
        ? 'Renove a sessão para reconectar; não há repetição automática de GPS.'
        : 'Sem reconexão automática. Acesso pode ter sido encerrado ou revogado.'}`;
    };
  };
  const load = button('Carregar viagens em andamento', async () => {
    load.disabled = true;
    close();
    try {
      rows = await allRecords('/api/travels/?status=in_progress');
      travel.replaceChildren(element('option', 'Selecione uma viagem', { value: '' }));
      for (const row of rows) travel.append(element('option', `${recordLabel(row)} — ${row.direction}`, { value: row.id }));
      status.textContent = `${rows.length} viagens autorizadas em andamento.`;
    } catch (error) { status.textContent = errorText(error); }
    finally { load.disabled = false; }
  });
  const http = button('Consultar última posição por HTTP', async () => {
    http.disabled = true;
    clearPosition();
    try {
      if (!travel.value) throw new Error('Escolha uma viagem.');
      const { data } = await request('GET', `/api/travels/${travel.value}/location/`);
      showPosition(data);
      status.textContent = 'Consulta HTTP concluída; não é acompanhamento contínuo.';
    } catch (error) { status.textContent = errorText(error); }
    finally { http.disabled = false; }
  });
  sender.append(' ', button('Obter um ponto do GPS (com permissão)', () => {
    if (!navigator.geolocation) { status.textContent = 'GPS indisponível neste contexto.'; return; }
    navigator.geolocation.getCurrentPosition(
      point => { latitude.value = point.coords.latitude; longitude.value = point.coords.longitude; status.textContent = 'GPS preenchido; nada foi enviado. Confirme o envio manualmente.'; },
      () => { status.textContent = 'Não foi possível obter o GPS. Nenhuma posição foi enviada.'; },
      { maximumAge: 0, timeout: 10000 },
    );
  }), ' ', element('button', 'Enviar este ponto agora', { type: 'submit' }));
  sendForm.addEventListener('submit', event => {
    event.preventDefault();
    if (sender.disabled || socket?.readyState !== WebSocket.OPEN || waiting) return;
    if (!confirm('Enviar estas coordenadas reais para esta viagem agora?')) return;
    waiting = true;
    const submit = sender.querySelector('button[type="submit"]');
    submit.disabled = true;
    socket.send(JSON.stringify({ latitude: Number(latitude.value), longitude: Number(longitude.value), recorded_at: new Date().toISOString() }));
    status.textContent = 'Ponto enviado; aguarde a confirmação ou recusa do servidor. Não é um evento de presença.';
    // Evita duplo clique; o limite autoritativo continua sendo o do servidor.
    setTimeout(() => { waiting = false; submit.disabled = false; }, 2500);
  });
  travel.addEventListener('change', () => { close(); status.textContent = 'Seleção alterada; conecte explicitamente.'; });
  sessionEvents.addEventListener('changed', () => close());
  sessionEvents.addEventListener('refreshed', () => { if (wanted) connect(); });
  window.addEventListener('pagehide', () => close());
  section.append(load, ' ', travel, ' ', button('Conectar WebSocket', connect), ' ', button('Desconectar', () => {
    close(); status.textContent = 'Desconectado manualmente.';
  }), ' ', http, status, position, lastUpdate, sendForm);
  parent.append(section);
}
