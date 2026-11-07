/**
 * FloodSense AI — script.js
 * Versão: 3.4 (frontend) | TCC — Sistemas de Informação
 *
 * ÍNDICE:
 *  01. Dados simulados (sensores IoT)
 *  02. Estado global da aplicação
 *  03. Funções utilitárias
 *  03b. Previsão da IA (Firebase /ai_predictions)
 *  04. Autenticação (togglePassword / logout / bootApp)
 *  05. Simulação de dados IoT (fetchIoTData)
 *  06. Sistema de navegação (navigate / renderScreen)
 *  07. Tela: Dashboard
 *  08. Tela: Sensores
 *  09. Tela: Mapa Interativo (Leaflet)
 *  10. Tela: IA & Previsões
 *  11. Tela: Análise Gráfica
 *  12. Tela: Alertas
 *  13. Tela: Relatórios
 *  14. Tela: Configurações
 *  15. Toast Notifications
 *  16. Utilitários de UI (clock, sidebar)
 *  17. Inicialização
 *
 * CHANGELOG v3.6
 *  - Botão "Enviar alerta" no Dashboard: grava um pedido em /pedidos_alerta/FS-001
 *    (exige login). O alerta_telegram.py envia a mensagem ao celular.
 *
 * CHANGELOG v3.5
 *  - Mapa base trocado para Esri World Street Map (visual de mapa de ruas, sem chave de API).
 *
 * CHANGELOG v3.4
 *  - Login agora é feito no index.html (Firebase Authentication).
 *    Removido handleLogin e as credenciais de demonstração.
 *  - bootApp() marca state.loggedIn = true (antes feito pelo handleLogin).
 *
 * CHANGELOG v3.3 — ÚNICA FONTE DE VERDADE PARA O NÍVEL ATUAL DO FS-001
 *  - Nível atual (cm): SOMENTE GET /sensors/FS-001.json → campo "level".
 *    Lido por fetchCurrentRealSensor() e guardado em
 *    state.realSensorReading. Todas as telas usam getCurrentRealLevel().
 *  - current_level_cm de /ai_predictions não representa mais o nível atual
 *    (continua sendo lido no payload apenas como informação/debug).
 *  - Sem fallback para histórico nem para valor simulado: se
 *    /sensors/FS-001.json estiver indisponível, o FS-001 fica OFFLINE e a
 *    interface mostra "Sem leitura".
 *  - Previsão: /ai_predictions/FS-001.json (inalterado).
 *  - Histórico/gráfico da IA: /sensor_history_treinamento/FS-001.json
 *    (inalterado).
 *
 * CHANGELOG v3.2
 *  - generated_at (UTC) é convertido para America/Sao_Paulo apenas na
 *    exibição; o timestamp original é usado para calcular a idade da previsão.
 *  - Tela de IA mostra os dados atuais do modelo V4 Progressivo publicados
 *    pelo Python (algoritmo, modo, lags, versão, MAE de teste). Campos
 *    ausentes aparecem como "—". Nenhum valor é inventado.
 *  - Status vem do backend (normal / warning / critical).
 */

/* ═══════════════════════════════════════════════════════════════════
   01. DADOS SIMULADOS — BASE DE SENSORES IoT
═══════════════════════════════════════════════════════════════════ */

/* Realtime Database (sem "https://" e sem barra final).
   Deixe como '' para rodar 100% simulado. */
const FIREBASE_HOST = 'floodsense-ai-7a6b9-default-rtdb.firebaseio.com';
const FIREBASE_SENSOR_ID = 'FS-001';

/* LEGADO: não é mais usado como trava. A previsão é exibida quando o
   Firebase publica um valor numérico em predicted_level_60min_cm com
   real_sensor_compatible === true (unidade cm). */
const CALIBRATION_VALIDATED = false;
const VALID_STATUS = ['normal', 'warning', 'critical'];

/* Intervalo de atualização automática da previsão da IA (ms) */
const AI_POLL_MS = 10000;
/* Intervalo de atualização do sensor real FS-001 (ms) */
const SENSOR_POLL_MS = 3000;
/* Previsão com mais de N minutos é marcada como desatualizada */
const AI_STALE_MIN = 30;

/* Posição FIXA do sensor físico FS-001 (faculdade):
   R. da Paz, 797 - Chácara Santo Antônio, São Paulo - SP, 04713-000.
   Coordenadas estáticas — NÃO usa geolocalização/GPS do navegador. */
const FS001_COORDS = { lat: -23.62986, lng: -46.70126 };
/* Zoom inicial do mapa (cobre a cidade de São Paulo e todos os marcadores) */
const MAP_INITIAL_ZOOM = 11;

const SENSORS_BASE = [
  {
    id: 'FS-001',
    name: 'Sensor Centro',
    location: 'R. da Paz, 797 - Chácara Santo Antônio',
    bairro: 'Chácara Santo Antônio',
    lat: FS001_COORDS.lat,
    lng: FS001_COORDS.lng,
    level: 115,
    temp: 23.4,
    humidity: 88,
    status: 'critical',
    lastRead: '09:14:32'
  },
  {
    id: 'FS-002',
    name: 'Sensor Zona Norte',
    location: 'Av. Cruzeiro do Sul, Santana',
    bairro: 'Zona Norte',
    lat: -23.5141,
    lng: -46.6322,
    level: 92,
    temp: 22.8,
    humidity: 91,
    status: 'critical',
    lastRead: '09:14:28'
  },
  {
    id: 'FS-003',
    name: 'Sensor Zona Sul',
    location: 'Av. João Dias, Santo Amaro',
    bairro: 'Zona Sul',
    lat: -23.6550,
    lng: -46.7000,
    level: 85,
    temp: 24.1,
    humidity: 82,
    status: 'warning',
    lastRead: '09:14:15'
  },
  {
    id: 'FS-004',
    name: 'Sensor Zona Leste',
    location: 'Av. Radial Leste, Tatuapé',
    bairro: 'Zona Leste',
    lat: -23.5441,
    lng: -46.5718,
    level: 68,
    temp: 25.0,
    humidity: 74,
    status: 'warning',
    lastRead: '09:13:55'
  },
  {
    id: 'FS-005',
    name: 'Sensor Zona Oeste',
    location: 'Av. Ermano Marchetti, Lapa',
    bairro: 'Zona Oeste',
    lat: -23.5177,
    lng: -46.7167,
    level: 42,
    temp: 26.3,
    humidity: 61,
    status: 'normal',
    lastRead: '09:14:40'
  },
  {
    id: 'FS-006',
    name: 'Sensor Marginal Tietê',
    location: 'Marginal Tietê, KM 12',
    bairro: 'Limão',
    lat: -23.5118,
    lng: -46.6535,
    level: 78,
    temp: 21.9,
    humidity: 93,
    status: 'warning',
    lastRead: '09:13:12'
  },
  {
    id: 'FS-007',
    name: 'Sensor Pinheiros',
    location: 'Av. Eusébio Matoso, Pinheiros',
    bairro: 'Pinheiros',
    lat: -23.5679,
    lng: -46.6964,
    level: 55,
    temp: 25.7,
    humidity: 70,
    status: 'normal',
    lastRead: '09:14:38'
  },
  {
    id: 'FS-008',
    name: 'Sensor Jabaquara',
    location: 'Av. Jabaquara, Jabaquara',
    bairro: 'Jabaquara',
    lat: -23.6200,
    lng: -46.6380,
    level: 33,
    temp: 27.1,
    humidity: 58,
    status: 'normal',
    lastRead: '09:14:41'
  },
  {
    id: 'FS-009',
    name: 'Sensor Penha',
    location: 'Rua Dr. João Ribeiro, Penha',
    bairro: 'Penha',
    lat: -23.5272,
    lng: -46.5283,
    level: 47,
    temp: 24.8,
    humidity: 66,
    status: 'normal',
    lastRead: '09:14:22'
  },
  {
    id: 'FS-010',
    name: 'Sensor Guarulhos',
    location: 'Av. Guarulhos, Mandaqui',
    bairro: 'Mandaqui',
    lat: -23.4958,
    lng: -46.6283,
    level: 61,
    temp: 23.3,
    humidity: 79,
    status: 'warning',
    lastRead: '09:12:58'
  },
  {
    id: 'FS-011',
    name: 'Sensor Brooklin',
    location: 'Av. Santo Amaro, Brooklin',
    bairro: 'Brooklin',
    lat: -23.6035,
    lng: -46.6929,
    level: 28,
    temp: 27.8,
    humidity: 54,
    status: 'normal',
    lastRead: '09:14:44'
  },
  {
    id: 'FS-012',
    name: 'Sensor Campo Limpo',
    location: 'Estrada do Campo Limpo',
    bairro: 'Campo Limpo',
    lat: -23.6418,
    lng: -46.7488,
    level: 0,
    temp: 0,
    humidity: 0,
    status: 'offline',
    lastRead: 'SEM SINAL'
  }
];

/* FS-001 sem leitura real: offline, sem nível (nenhum valor inventado) */
const fs001Offline = s => ({
  ...s, level: null, temp: null, humidity: null,
  status: 'offline', source: 'offline', lastRead: 'SEM LEITURA'
});

/* Histórico simulado de 24h para gráficos */
const HISTORY_24H = {
  labels: ['00h','01h','02h','03h','04h','05h','06h','07h','08h','09h','10h','11h',
           '12h','13h','14h','15h','16h','17h','18h','19h','20h','21h','22h','23h'],
  centro: [60,65,72,80,90,100,108,112,115,114,112,108,100,90,82,78,74,70,68,65,62,60,58,57],
  norte:  [45,50,58,65,74,80,85,88,92,91,89,85,80,74,68,62,58,54,51,48,46,44,43,42],
  sul:    [40,44,50,56,63,70,76,80,85,84,82,78,72,67,62,58,54,51,48,46,44,42,40,39],
  media:  [48,52,59,67,75,83,89,93,97,96,94,90,84,77,70,66,62,58,55,53,51,49,47,46]
};

/* Alertas históricos */
const ALERTS_DATA = [
  { id: 1, type: 'critical', icon: '🚨', zone: 'Centro — Praça da Sé', sensor: 'DEMO',
    msg: 'Cenário de demonstração: nível de 115cm. Não é leitura do ESP32.', time: '09:14', badge: 'CRÍTICO' },
  { id: 2, type: 'critical', icon: '🚨', zone: 'Zona Norte — Santana', sensor: 'FS-002',
    msg: 'Dado simulado: nível de 92cm, acima do limite crítico (90cm). Não é leitura do ESP32.', time: '09:12', badge: 'CRÍTICO' },
  { id: 3, type: 'warning', icon: '⚠️', zone: 'Zona Sul — Santo Amaro', sensor: 'FS-003',
    msg: 'Nível em 85cm. Tendência crescente. Monitoramento intensificado.', time: '09:10', badge: 'ATENÇÃO' },
  { id: 4, type: 'warning', icon: '⚠️', zone: 'Marginal Tietê — KM12', sensor: 'FS-006',
    msg: 'Umidade do solo em 93%. Possível saturação hídrica (dado simulado).', time: '09:05', badge: 'ATENÇÃO' },
  { id: 5, type: 'warning', icon: '⚠️', zone: 'Mandaqui', sensor: 'FS-010',
    msg: 'Nível em 61cm. Equipes em standby.', time: '08:55', badge: 'ATENÇÃO' },
  { id: 6, type: 'info', icon: '✅', zone: 'Jabaquara', sensor: 'FS-008',
    msg: 'Situação normalizada. Nível caiu para 33cm após recuo das chuvas.', time: '08:30', badge: 'NORMAL' },
  { id: 7, type: 'info', icon: '✅', zone: 'Pinheiros', sensor: 'FS-007',
    msg: 'Leitura estável. Nível dentro dos parâmetros normais (55cm).', time: '08:00', badge: 'NORMAL' },
  { id: 8, type: 'system', icon: '⚫', zone: 'Sistema — Campo Limpo', sensor: 'FS-012',
    msg: 'Sensor FS-012 sem comunicação há 52 minutos. Equipe de manutenção acionada via sistema.', time: '07:22', badge: 'OFFLINE' }
];

/* ═══════════════════════════════════════════════════════════════════
   02. ESTADO GLOBAL DA APLICAÇÃO
═══════════════════════════════════════════════════════════════════ */
const FloodSense = {

  /** Estado reativo da aplicação */
  state: {
    loggedIn:    false,
    currentScreen: 'dashboard',
    /* FS-001 começa SEM LEITURA (offline) até /sensors/FS-001.json responder.
       Os demais sensores são simulados. */
    sensors:     JSON.parse(JSON.stringify(SENSORS_BASE)).map(s => s.id === FIREBASE_SENSOR_ID ? fs001Offline(s) : { ...s, source: 'simulated' }),
    alerts:      ALERTS_DATA.filter(a => a.sensor !== 'DEMO').map(a => ({ ...a, zone: a.zone + ' · SIMULADO' })),
    sidebarOpen: false,
    iotInterval: null,
    clockInterval: null,
    chartInstances: {},
    leafletMap: null,
    leafletMarkers: [],
    aiInterval: null,
    predictionInterval: null, // polling de /ai_predictions (global, todas as telas)
    aiPrediction: null,       // previsão normalizada (inicializada logo após este objeto)
    aiPredictionFetchedAt: null,
    lastAIModel: null,        // último nome de modelo recebido do Firebase (só exibição)
    realSensor: null,         // estado do painel do FS-001 (Firebase)
    realSensorReading: null,  // ÚNICA fonte do nível atual do FS-001: { id, level, distance, status, timestamp, source:"real" } ou null
    searchQuery: '',
    filterStatus: 'all',
    sortField: 'id',
    sortDir: 'asc',
    currentPage: 1,
    rowsPerPage: 8,
  },

  /* ═════════════════════════════════════════════
     03. FUNÇÕES UTILITÁRIAS
  ═════════════════════════════════════════════ */

  /** Retorna badge HTML conforme status do sensor */
  getStatusBadge(status) {
    const map = {
      normal:   ['badge-green',  '●', 'NORMAL'],
      warning:  ['badge-yellow', '●', 'ATENÇÃO'],
      critical: ['badge-red',    '●', 'CRÍTICO'],
      offline:  ['badge-gray',   '●', 'OFFLINE']
    };
    const [cls, dot, label] = map[status] || map.offline;
    return `<span class="badge ${cls}">${dot} ${label}</span>`;
  },

  /** Retorna cor do nível de água conforme valor */
  getLevelColor(level, status) {
    if (status === 'offline') return 'color: var(--text-muted)';
    if (status === 'critical') return 'color: var(--red)';
    if (status === 'warning')  return 'color: var(--yellow)';
    return 'color: var(--green)';
  },

  /** Retorna classe CSS para linha da tabela de nível */
  getLevelClass(status) {
    if (status === 'critical') return 'level-critical';
    if (status === 'warning')  return 'level-attention';
    return 'level-normal';
  },

  /** Formata número com unidade */
  fmt(val, unit = '') {
    if (val === 0 || val === null) return '—';
    return `${val}${unit}`;
  },

  /** Valor com unidade; '—' quando não medido */
  fmtVal(v, unit = '') { return (v === null || v === undefined || v === '') ? '—' : `${v}${unit}`; },

  /** Etiqueta de origem do dado: REAL / SIMULADO / SEM LEITURA */
  getSourceTag(s) {
    if (s.source === 'real')    return '<span class="data-tag data-tag-real">REAL</span>';
    if (s.source === 'offline') return '<span class="data-tag data-tag-sim">SEM LEITURA</span>';
    return '<span class="data-tag data-tag-sim">SIMULADO</span>';
  },

  /** Apresentação: instante (ms) → dd/mm/aaaa hh:mm em America/Sao_Paulo.
      Não altera o timestamp original (usado só para exibir). */
  fmtSaoPaulo(ms) {
    const p = {};
    new Intl.DateTimeFormat('pt-BR', {
      timeZone: 'America/Sao_Paulo',
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false
    }).formatToParts(new Date(ms)).forEach(x => { p[x.type] = x.value; });
    return `${p.day}/${p.month}/${p.year} ${p.hour === '24' ? '00' : p.hour}:${p.minute}`;
  },

  /** Algoritmo amigável (ET_... / ExtraTreesRegressor → ExtraTrees) */
  friendlyAlgo(p) {
    const a = (p && p.algorithm) || '';
    if (/gradient|^GBR/i.test(a)) return 'GradientBoosting';
    if (/^ET/i.test(a) || /extra/i.test(a)) return 'ExtraTrees';
    return (p && p.model) || a || null;
  },

  /** "ExtraTrees · LAG_15" ou null */
  aiModelLabel(p) {
    const modo = (p && /^(STARTUP|LAG_5|LAG_15|FULL)$/.test(p.model || '')) ? p.model : ((p && p.mode && p.mode !== 'CORE') ? p.mode : null);
    const s = [this.friendlyAlgo(p), modo].filter(Boolean).join(' · ');
    return s || null;
  },

  /** Lucide tolerante a falha de CDN */
  icons() { if (window.lucide) window.lucide.createIcons(); },

  /** Converte para número finito ou null (nunca NaN/undefined) */
  parseNum(v) {
    if (v === null || v === undefined || v === '' || typeof v === 'boolean' || typeof v === 'object') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  },

  /** Escapa texto vindo de fora (Firebase) antes de usar em innerHTML */
  esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  },

  /** "72.4 cm" ou "—" quando não há número válido */
  fmtCm(v, d = 1) {
    const n = this.parseNum(v);
    return n === null ? '—' : `${n.toFixed(d)} cm`;
  },

  /** Nível atual do FS-001 formatado: "72.4 cm" ou "Sem leitura" (FS-001 offline) */
  fmtCurrentLevel() {
    const n = this.getCurrentRealLevel();
    return n === null ? 'Sem leitura' : `${n.toFixed(1)} cm`;
  },

  /** Define textContent (e opcionalmente a cor) de um elemento, se ele existir na tela atual */
  setText(id, text, color) {
    const el = document.getElementById(id);
    if (!el) return null;
    el.textContent = text;
    if (color !== undefined) el.style.color = color;
    return el;
  },

  /** Painel do sensor físico FS-001 (dados vindos do Firebase) */
  setRealPanel(d) {
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    const badge = document.getElementById('real-sensor-status-badge');
    this.state.realSensor = { ok: !!d };
    if (!d) {
      set('real-level', '--');
      set('real-distance', '--');
      set('real-status', 'OFFLINE');
      set('real-connection-text', 'FS-001 offline · aguardando ESP32/Firebase');
      set('real-updated', 'sem leitura no momento');
      if (badge) { badge.textContent = '○ SEM LEITURA'; badge.className = 'real-status-badge'; }
      return;
    }
    set('real-level', d.level.toFixed(1));
    set('real-distance', d.distance === null ? '--' : d.distance.toFixed(1));   // nunca derivado de 100 - nível
    set('real-status', d.status === 'critical' ? 'CRÍTICO' : d.status === 'warning' ? 'ATENÇÃO' : 'NORMAL');
    let when = 'consultado às ' + new Date().toLocaleTimeString('pt-BR');
    const ts = Number(d.timestamp);
    if (Number.isFinite(ts) && ts > 1e9) {
      const age = Math.round((Date.now() - (ts > 1e12 ? ts : ts * 1000)) / 60000);
      when = age <= 0 ? 'atualizado agora' : `leitura há ${age} min`;
    }
    set('real-updated', when);
    set('real-connection-text', 'conectado ao Firebase');
    if (badge) {
      badge.textContent = '● ONLINE · FS-001';
      badge.className = 'real-status-badge ' + (d.status === 'critical' ? 'critical' : d.status === 'warning' ? 'warning' : 'online');
    }
  },

  /** Destrói uma instância de Chart.js pelo ID do canvas */
  destroyChart(id) {
    if (this.state.chartInstances[id]) {
      this.state.chartInstances[id].destroy();
      delete this.state.chartInstances[id];
    }
  },

  /** Cria Chart.js e salva referência */
  makeChart(canvasId, config) {
    this.destroyChart(canvasId);
    const ctx = document.getElementById(canvasId);
    if (!ctx || typeof Chart === 'undefined') return null;
    const chart = new Chart(ctx, config);
    this.state.chartInstances[canvasId] = chart;
    return chart;
  },

  /** Configuração global padrão do Chart.js — tema claro */
  chartDefaults() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0B1F3A',
          borderColor: '#1e293b',
          borderWidth: 1,
          titleColor: '#ffffff',
          bodyColor: '#cbd5e1',
          padding: 10,
          cornerRadius: 8,
        }
      },
      scales: {
        x: {
          ticks: { color: '#64748b', font: { size: 10, family: 'JetBrains Mono' } },
          grid:  { color: 'rgba(11,31,58,0.08)' }
        },
        y: {
          ticks: { color: '#64748b', font: { size: 10, family: 'JetBrains Mono' } },
          grid:  { color: 'rgba(11,31,58,0.08)' }
        }
      }
    };
  },

  /* ═════════════════════════════════════════════
     03b. PREVISÃO DA IA — Firebase /ai_predictions/FS-001

     O Python publica em /ai_predictions/FS-001.json, entre outros:
       current_level_cm, predicted_level_60min_cm, status
       ("normal" | "warning" | "critical"), generated_at (UTC, ISO),
       horizon_minutes, model (ex.: "ExtraTrees"), sensor_unit,
       real_sensor_compatible, prediction_mode (STARTUP | LAG_5 |
       LAG_15 | FULL), available_lags, model_algorithm, model_version,
       selection_mae_test_cm.

     REGRAS:
       • Disponível só quando predicted_level_60min_cm é número finito E
         real_sensor_compatible === true (sensor_unit, se existir, = "cm").
       • Nó vazio / null / erro de rede → "Aguardando previsão da IA".
       • Nenhum valor simulado é usado aqui.
       • current_level_cm é lido só como informação/debug; o NÍVEL ATUAL
         exibido na interface vem exclusivamente de /sensors/FS-001.json.
  ═════════════════════════════════════════════ */

  /** Estrutura padrão (sem previsão). reason: loading | empty | no_value | incompatible | error | ok */
  emptyPrediction(reason = 'empty') {
    return {
      available: false, reason,
      predicted: null, current: null, status: null,
      generatedLabel: '—', ageMin: null, stale: false,
      horizon: 60, model: null, unit: null,
      compatible: false, message: '', historyRecords: null,
      mode: null, algorithm: null, version: null, lags: [], mae: null
    };
  },

  /**
   * Interpreta generated_at. O Python grava em UTC (com fuso explícito):
   * a conversão para America/Sao_Paulo é SOMENTE visual; a idade é calculada
   * com o instante original.
   */
  parsePredictionTime(value) {
    const out = { label: '—', ageMin: null };
    if (value === null || value === undefined || value === '') return out;

    if (typeof value === 'string') {
      const txt = value.trim();

      // ISO com fuso explícito (Z ou ±hh:mm) → converte para São Paulo
      if (/(Z|[+-]\d{2}:?\d{2})$/i.test(txt)) {
        const t0 = Date.parse(txt);
        if (Number.isFinite(t0)) {
          out.label = this.fmtSaoPaulo(t0);
          out.ageMin = Math.max(0, Math.round((Date.now() - t0) / 60000));
          return out;
        }
      }

      // ISO sem fuso: mostrado como veio (não é possível converter sem inventar o fuso)
      const m = txt.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
      if (m) {
        out.label = `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}`;
        return out;
      }
    }

    let ms = null;
    const n = this.parseNum(value);
    if (n !== null) ms = n > 1e12 ? n : (n > 1e9 ? n * 1000 : null);   // epoch em ms ou s
    else { const t = Date.parse(String(value)); if (Number.isFinite(t)) ms = t; }
    if (ms === null) return out;

    out.label = this.fmtSaoPaulo(ms);
    out.ageMin = Math.max(0, Math.round((Date.now() - ms) / 60000));
    return out;
  },

  /** Normaliza o JSON bruto do Firebase (aceita null, vazio, tipos errados) */
  normalizePrediction(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return this.emptyPrediction('empty');

    const p = this.emptyPrediction('no_value');
    p.predicted = this.parseNum(raw.predicted_level_60min_cm);
    p.current   = this.parseNum(raw.current_level_cm);   // informação/debug apenas — NÃO é o nível atual da interface
    p.horizon   = this.parseNum(raw.horizon_minutes) ?? 60;
    p.historyRecords = this.parseNum(raw.history_records);
    p.model   = (typeof raw.model === 'string' && raw.model.trim()) ? raw.model.trim() : null;
    p.unit    = (typeof raw.sensor_unit === 'string' && raw.sensor_unit.trim()) ? raw.sensor_unit.trim().toLowerCase() : null;
    p.message = (typeof raw.message === 'string') ? raw.message.trim() : '';
    p.compatible = raw.real_sensor_compatible === true && (p.unit === null || p.unit === 'cm');

    // Campos do modelo V4 Progressivo (ausentes → null / vazio, nunca inventados)
    const txt = v => (typeof v === 'string' && v.trim()) ? v.trim() : null;
    p.mode      = txt(raw.prediction_mode) || txt(raw.model_mode);
    p.algorithm = txt(raw.model_algorithm) || txt(raw.algorithm);
    p.version   = txt(raw.model_version);
    p.lags      = Array.isArray(raw.available_lags) ? raw.available_lags.map(String) : [];
    p.mae       = this.parseNum(raw.selection_mae_test_cm);

    // Status: respeita o enviado pelo backend (sem segunda regra)
    const st = String(raw.status || '').toLowerCase();
    p.status = VALID_STATUS.includes(st) ? st : null;

    const t = this.parsePredictionTime(raw.generated_at);
    p.generatedLabel = t.label;
    p.ageMin = t.ageMin;
    p.stale = t.ageMin !== null && t.ageMin > AI_STALE_MIN;

    if (p.predicted === null) {
      p.reason = 'no_value';
    } else if (!p.compatible) {
      p.reason = 'incompatible';
    } else if (p.stale) {
      // Previsão antiga: não é tratada como atual (valor fica guardado só para referência)
      p.reason = 'stale';
      p.available = false;
    } else {
      p.reason = 'ok';
      p.available = true;
    }
    return p;
  },

  /** Idade em minutos por extenso (ex.: "14 dias e 18 h") */
  fmtAgeMin(min) {
    if (min === null || min === undefined) return '—';
    if (min < 60) return `${min} min`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h} h ${min % 60} min`;
    const d = Math.floor(h / 24);
    return `${d} dia${d > 1 ? 's' : ''} e ${h % 24} h`;
  },

  /** Texto "indisponível" conforme o motivo */
  aiWaitingText(p) {
    switch (p && p.reason) {
      case 'stale':        return `Previsão desatualizada (gerada há ${this.fmtAgeMin(p.ageMin)}). Aguardando nova previsão da IA.`;
      case 'loading':      return 'Consultando previsão da IA...';
      case 'error':        return 'Não foi possível consultar a previsão no Firebase';
      case 'incompatible': return 'Previsão recebida, mas não marcada como compatível com cm';
      case 'no_value':     return 'Aguardando previsão da IA (sem valor numérico)';
      default:             return 'Aguardando previsão da IA';
    }
  },

  /** Cores/rótulos por status da previsão */
  aiStatusMeta(status) {
    const map = {
      normal:   { label: 'NORMAL',  color: 'var(--green)',  kpi: 'green',  ic: 'ic-green',  val: 'col-green' },
      warning:  { label: 'ATENÇÃO', color: 'var(--yellow)', kpi: 'yellow', ic: 'ic-yellow', val: 'col-yellow' },
      critical: { label: 'CRÍTICO', color: 'var(--red)',    kpi: 'red',    ic: 'ic-red',    val: 'col-red' }
    };
    return map[status] || { label: '—', color: 'var(--text-muted)', kpi: 'blue', ic: 'ic-blue', val: 'col-blue' };
  },

  /** Sensor FS-001 com dado REAL (null se estiver offline / sem leitura) */
  getRealSensor() {
    return this.state.sensors.find(x => x.source === 'real') || null;
  },

  /**
   * NÍVEL ATUAL DO FS-001 (cm) — ÚNICA função usada pela interface.
   * Retorna SOMENTE state.realSensorReading.level (de /sensors/FS-001.json)
   * ou null se não houver leitura válida. Sem fallback para IA, histórico
   * ou valor simulado.
   */
  getCurrentRealLevel() {
    const r = this.state.realSensorReading;
    return (r && Number.isFinite(r.level)) ? r.level : null;
  },

  /** Resumo textual da previsão (Análise Gráfica / Relatórios) */
  aiSummary() {
    const p = this.state.aiPrediction || this.emptyPrediction('loading');
    if (p.available) {
      const meta = this.aiStatusMeta(p.status);
      return {
        ok: true, color: meta.color,
        text: `Previsão IA +${p.horizon} min (FS-001): ${this.fmtCm(p.predicted)} · ${meta.label} · dado real do Firebase`,
        short: this.fmtCm(p.predicted)
      };
    }
    return { ok: false, color: 'var(--yellow)', text: this.aiWaitingText(p), short: 'aguardando previsão' };
  },

  /** Nome do modelo recebido do Firebase (ou o último conhecido); null se nunca recebido */
  getAIModelName() {
    const p = this.state.aiPrediction;
    if (p && p.model) this.state.lastAIModel = p.model;
    return this.state.lastAIModel || null;
  },

  /** Status visual da IA, baseado no estado REAL da previsão */
  aiStatusText(p) {
    p = p || this.state.aiPrediction || this.emptyPrediction('loading');
    if (p.available) return `IA ONLINE · +${p.horizon} MIN`;
    if (p.reason === 'stale') return 'IA · PREVISÃO DESATUALIZADA';
    if (p.reason === 'error') return 'IA · SEM CONEXÃO';
    return 'IA AGUARDANDO PREVISÃO';
  },

  aiStatusColor(p) {
    p = p || this.state.aiPrediction || this.emptyPrediction('loading');
    if (p.available) return 'var(--green)';
    if (p.reason === 'error') return 'var(--red)';
    return 'var(--yellow)';
  },

  /** Rodapé da barra lateral: modelo, estado e hora da última previsão (ids no index.html) */
  updateSidebarAIStatus() {
    const st = document.getElementById('sb-ai-status');
    if (!st) return;
    const p = this.state.aiPrediction || this.emptyPrediction('loading');
    st.textContent = p.available ? 'ONLINE' : (p.reason === 'stale' ? 'DESATUALIZADA' : (p.reason === 'error' ? 'SEM CONEXÃO' : 'AGUARDANDO'));
    st.style.color = this.aiStatusColor(p);
    const m = document.getElementById('sb-ai-model');
    if (m) m.textContent = (p.available && this.aiModelLabel(p)) || 'V4 Progressivo';
    const u = document.getElementById('sb-upd');
    if (u) u.textContent = p.available ? p.generatedLabel.slice(-5) : 'aguardando';
  },

  /** Busca /ai_predictions/FS-001.json, normaliza e atualiza a UI. Nunca lança erro. */
  async fetchAIPrediction() {
    if (!FIREBASE_HOST || !FIREBASE_SENSOR_ID) {
      this.state.aiPrediction = this.emptyPrediction('empty');
    } else {
      try {
        const url = `https://${FIREBASE_HOST}/ai_predictions/${FIREBASE_SENSOR_ID}.json`;
        const response = await fetch(url, { cache: 'no-store' });
        if (!response.ok) throw new Error(`IA HTTP ${response.status}`);
        const raw = await response.json();          // pode ser null (nó inexistente/vazio)
        this.state.aiPrediction = this.normalizePrediction(raw);
      } catch (error) {
        console.warn('[FloodSense] Erro ao consultar /ai_predictions:', error);
        this.state.aiPrediction = this.emptyPrediction('error');
      }
    }
    this.state.aiPredictionFetchedAt = Date.now();
    if (this.state.loggedIn) this.applyAIPredictionToUI();
  },

  /** Inicia o polling automático da previsão (sem recarregar a página) */
  startAIPredictionPolling() {
    clearInterval(this.state.predictionInterval);
    this.fetchAIPrediction();
    this.state.predictionInterval = setInterval(() => this.fetchAIPrediction(), AI_POLL_MS);
  },

  /** Propaga a previsão para a tela que estiver aberta */
  applyAIPredictionToUI() {
    this.updateSidebarAIStatus();
    if (this.state.currentScreen === 'dashboard') {
      this.updateDashboardKPIs();
      this.updateDashboardAICard();
    }
    if (this.state.currentScreen === 'ai') this.updateAIScreen();
  },

  /** Card "IA · Previsão FS-001" do Dashboard */
  updateDashboardAICard() {
    if (!document.getElementById('dash-ai-card')) return;
    const p = this.state.aiPrediction || this.emptyPrediction('loading');
    const hasCur = this.getCurrentRealLevel() !== null;
    this.setText('dash-ai-current', this.fmtCurrentLevel(), hasCur ? 'var(--blue)' : 'var(--text-muted)');

    if (p.available) {
      const meta = this.aiStatusMeta(p.status);
      this.setText('dash-ai-pred', this.fmtCm(p.predicted), meta.color);
      this.setText('dash-ai-status', meta.label, meta.color);
      this.setText('dash-ai-time', p.generatedLabel, 'var(--text-secondary)');
      this.setText('dash-ai-note', p.stale ? 'desatualizada' : `atualização automática · ${AI_POLL_MS / 1000}s`);
      this.setText('dash-ai-msg',
        p.stale
          ? `Previsão desatualizada (gerada há ${p.ageMin} min). Aguardando nova previsão da IA.`
          : `Previsão de +${p.horizon} min publicada${this.aiModelLabel(p) ? ' · ' + this.aiModelLabel(p) : ''} · valor real do Firebase.`,
        p.stale ? 'var(--yellow)' : 'var(--text-secondary)');
    } else {
      this.setText('dash-ai-pred', '—', 'var(--yellow)');
      this.setText('dash-ai-status', '—', 'var(--text-muted)');
      this.setText('dash-ai-time', '—', 'var(--text-muted)');
      this.setText('dash-ai-note', p.reason === 'error' ? 'sem conexão' : 'sem previsão');
      this.setText('dash-ai-msg', this.aiWaitingText(p), p.reason === 'error' ? 'var(--red)' : 'var(--yellow)');
    }
  },

  /** Tela IA & Previsões: KPIs, caixa de estado, informações do modelo e pipeline */
  updateAIScreen() {
    if (!document.getElementById('ai-current-level')) return;
    const p = this.state.aiPrediction || this.emptyPrediction('loading');
    const cur = this.getCurrentRealLevel();
    const box = document.getElementById('ai-status-box');
    const paint = (bg, border) => { if (box) { box.style.background = bg; box.style.borderColor = border; } };

    this.setText('ai-current-level', this.fmtCurrentLevel());
    this.setText('ai-current-status', cur !== null ? 'Sensor real · /sensors/FS-001' : 'FS-001 offline');
    this.setText('ai-info-model', this.aiModelLabel(p) || this.getAIModelName() || '—');
    this.setText('ai-info-horizon', `${p.horizon} min`);
    this.setText('ai-v4-algo', this.friendlyAlgo(p) || '—');
    this.setText('ai-v4-mode', p.mode || '—');
    this.setText('ai-v4-lags', p.lags && p.lags.length ? p.lags.join(', ') : '—');
    this.setText('ai-v4-version', p.version || '—');
    this.setText('ai-v4-mae', p.mae !== null && p.mae !== undefined ? this.fmtCm(p.mae, 2) : '—');

    if (p.available) {
      const meta = this.aiStatusMeta(p.status);
      this.setText('ai-prediction-value', this.fmtCm(p.predicted), meta.color);
      this.setText('ai-prediction-status', `Status previsto: ${meta.label}`);
      this.setText('ai-prediction-time', `Gerada em ${p.generatedLabel}${p.stale ? ' · desatualizada' : ''}`);
      this.setText('ai-compatibility', 'COMPATÍVEL', 'var(--green)');
      this.setText('ai-compat-note', `Sensor em ${p.unit || 'cm'}`);
      this.setText('ai-info-unit', p.unit || 'cm');
      this.setText('ai-pipe-icon', '✓', 'var(--green)');
      this.setText('ai-pipe-text', 'Modelo publicou previsão compatível com o sensor real (cm)');
      if (p.stale) {
        this.setText('ai-status-title', 'Previsão desatualizada', 'var(--yellow)');
        this.setText('ai-status-message', `A última previsão foi gerada há ${p.ageMin} min. Aguardando nova previsão da IA.`);
        paint('rgba(242,140,0,0.06)', 'rgba(242,140,0,0.22)');
      } else {
        this.setText('ai-status-title', 'Previsão disponível', 'var(--green)');
        this.setText('ai-status-message', `Previsão de +${p.horizon} min lida do Firebase (/ai_predictions/${FIREBASE_SENSOR_ID}). O modelo marcou a previsão como compatível com o sensor físico em cm. Atualização automática a cada ${AI_POLL_MS / 1000}s.`);
        paint('rgba(22,163,106,0.06)', 'rgba(22,163,106,0.22)');
      }
    } else {
      const isError = p.reason === 'error';
      const isIncompat = p.reason === 'incompatible';
      this.setText('ai-prediction-value', '—', 'var(--yellow)');
      this.setText('ai-prediction-status', this.aiWaitingText(p));
      this.setText('ai-prediction-time', 'Aguardando previsão da IA');
      this.setText('ai-compatibility', isIncompat ? 'INCOMPATÍVEL' : 'AGUARDANDO', isIncompat ? 'var(--red)' : 'var(--yellow)');
      this.setText('ai-compat-note', isIncompat ? 'Verifique unidade/flag' : 'Sem previsão publicada');
      this.setText('ai-info-unit', p.unit || '—');
      this.setText('ai-pipe-icon', '●', 'var(--yellow)');
      this.setText('ai-pipe-text', 'Aguardando o Python publicar a previsão em /ai_predictions');
      this.setText('ai-status-title', isError ? 'Falha ao consultar Firebase' : 'Aguardando previsão da IA', isError ? 'var(--red)' : 'var(--yellow)');
      this.setText('ai-status-message',
        isError
          ? 'Não foi possível ler /ai_predictions neste momento. Nenhum valor é exibido até a próxima consulta bem-sucedida.'
          : (p.message || `Ainda não há valor numérico em predicted_level_60min_cm no Firebase (/ai_predictions/${FIREBASE_SENSOR_ID}). Nenhuma previsão é simulada.`));
      if (isError) paint('rgba(220,69,69,0.06)', 'rgba(220,69,69,0.22)');
      else paint('rgba(242,140,0,0.06)', 'rgba(242,140,0,0.22)');
    }
  },

  /** Histórico bruto do Firebase → [{timestamp, level}] ordenado (descarta registros inválidos) */
  parseHistory(historyData) {
    const history = [];
    if (!historyData || typeof historyData !== 'object') return history;
    Object.entries(historyData).forEach(([key, value]) => {
      if (!value || typeof value !== 'object') return;
      const timestamp = this.parseNum(value.timestamp ?? key);
      const level = this.parseNum(value.level);
      if (timestamp === null || level === null) return;
      history.push({ timestamp, level });
    });
    history.sort((a, b) => a.timestamp - b.timestamp);
    return history;
  },

  /**
   * LEITURA ATUAL OFICIAL do FS-001 (valores em cm, sem conversão).
   * Única fonte: GET /sensors/FS-001.json → campo "level".
   * Sem fallback (nem histórico, nem IA, nem simulado).
   * Atualiza this.state.realSensorReading e devolve o objeto normalizado,
   * ou null (e zera o estado) se o sensor estiver indisponível.
   */
  async fetchCurrentRealSensor() {
    let reading = null;

    if (FIREBASE_HOST) {
      try {
        const url = `https://${FIREBASE_HOST}/sensors/${FIREBASE_SENSOR_ID}.json`;
        const response = await fetch(url, { cache: 'no-store' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const real = await response.json();                 // pode ser null
        const level = (real && typeof real === 'object') ? this.parseNum(real.level) : null;
        if (level === null) throw new Error('campo "level" ausente ou inválido');

        const st = String(real.status || '').toLowerCase();
        reading = {
          id: FIREBASE_SENSOR_ID,
          level: level,                                      // cm
          distance: this.parseNum(real.distance),            // null se ausente
          status: VALID_STATUS.includes(st) ? st : (level >= 90 ? 'critical' : level >= 60 ? 'warning' : 'normal'),
          timestamp: real.timestamp,
          source: 'real'
        };
      } catch (error) {
        console.warn('[FloodSense] /sensors/' + FIREBASE_SENSOR_ID + ' indisponível:', error);
        reading = null;
      }
    }

    this.state.realSensorReading = reading;
    return reading;
  },

  /* ═════════════════════════════════════════════
     04. AUTENTICAÇÃO
     O login é feito no index.html (Firebase Authentication).
     Aqui ficam apenas: mostrar/ocultar senha, sair e iniciar o app.
  ═════════════════════════════════════════════ */

  /** Mostra/oculta campo de senha */
  togglePassword() {
    const input = document.getElementById('input-password');
    input.type = input.type === 'password' ? 'text' : 'password';
  },

  /** Encerra sessão de visualização e volta ao login (o signOut do Firebase é feito no index.html) */
  logout() {
    this.state.loggedIn = false;
    clearInterval(this.state.iotInterval);
    clearInterval(this.state.clockInterval);
    clearInterval(this.state.predictionInterval);
    this.state.predictionInterval = null;
    this.state.aiPrediction = this.emptyPrediction('loading');
    this.state.realSensorReading = null;
    this.state.sensors = this.state.sensors.map(s => s.id === FIREBASE_SENSOR_ID ? fs001Offline(s) : s);
    if (this.state.leafletMap) {
      this.state.leafletMap.remove();
      this.state.leafletMap = null;
    }
    clearInterval(this.state.aiInterval);
    Object.keys(this.state.chartInstances).forEach(id => this.destroyChart(id));
    const loginBtn = document.getElementById('btn-login');
    if (loginBtn) {
      loginBtn.classList.remove('loading');
      loginBtn.innerHTML = '<i data-lucide="log-in"></i><span>Entrar no Sistema</span>';
    }
    document.getElementById('app-shell').hidden = true;
    document.getElementById('login-screen').style.display = 'flex';
    this.icons();
    this.showToast('info', 'Sessão encerrada', 'Você saiu do sistema com segurança.');
  },

  /* ═════════════════════════════════════════════
     ALERTA MANUAL PARA O CELULAR (Telegram)
     O botão grava um pedido em /pedidos_alerta/FS-001 no Firebase.
     O alerta_telegram.py (no computador) lê o pedido e envia a mensagem.
     Só funciona com login ativo: a regra do banco exige auth.
  ═════════════════════════════════════════════ */
  pedirAlertaTelegram() {
    const usuario = (typeof firebase !== 'undefined' && firebase.auth) ? firebase.auth().currentUser : null;
    if (!usuario) {
      this.showToast('warning', 'Login necessário', 'Entre no painel para enviar alertas ao celular.');
      return;
    }

    const agora = Date.now();
    const COOLDOWN_PEDIDO_MS = 2 * 60 * 1000;
    if (this._ultimoPedidoAlerta && agora - this._ultimoPedidoAlerta < COOLDOWN_PEDIDO_MS) {
      const falta = Math.ceil((COOLDOWN_PEDIDO_MS - (agora - this._ultimoPedidoAlerta)) / 1000);
      this.showToast('warning', 'Aguarde', `Você pode enviar outro alerta em ${falta} s.`);
      return;
    }

    if (!confirm('Enviar alerta para o celular com o nível atual do FS-001?')) return;

    try {
      firebase.database()
        .ref(`pedidos_alerta/${FIREBASE_SENSOR_ID}`)
        .push({
          criadoEm: firebase.database.ServerValue.TIMESTAMP,
          uid: usuario.uid,
          enviado: false
        });
      this._ultimoPedidoAlerta = agora;
      this.showToast('success', 'Pedido enviado', 'O alerta chega ao celular em até 1 minuto.');
    } catch (erro) {
      console.error('[FloodSense] Falha ao gravar pedido de alerta:', erro);
      this.showToast('critical', 'Falha ao enviar', 'Não foi possível registrar o pedido. Verifique a conexão.');
    }
  },

  /** Inicia o aplicativo após login bem-sucedido (chamado por mostrarApp() no index.html) */
  bootApp() {
    this.state.loggedIn = true;

    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app-shell').hidden = false;

    FloodSense.icons();

    // Inicia relógio
    this.startClock();

    // Inicia simulação IoT (+ leitura real do FS-001)
    this.startIoTSimulation();

    // Inicia polling da previsão da IA (Firebase /ai_predictions)
    this.startAIPredictionPolling();
    this.updateSidebarAIStatus();

    // Renderiza tela inicial
    this.navigate('dashboard');

    // Notificações de boas-vindas
    setTimeout(() => {
      this.showToast(
        'info',
        'Origem dos dados',
        'REAL: sensor FS-001 (ESP32 → Firebase). SIMULADOS: FS-002 a FS-012.'
      );
    }, 1500);

    setTimeout(() => {
      this.showToast(
        'info',
        'IA & Previsões',
        'A previsão de +60 min do FS-001 é lida do Firebase e só aparece quando o Python publica um valor numérico real.'
      );
    }, 3500);

  },

  /* ═════════════════════════════════════════════
     05. SIMULAÇÃO DE DADOS IoT

     Os sensores FS-002 a FS-012 são simulados. O FS-001 vem do
     Firebase (ESP32) e NUNCA é simulado: sem leitura → offline.
     Para uma API própria, descomente o bloco indicado em
     fetchIoTData() e troque a URL.
  ═════════════════════════════════════════════ */

  /**
   * Busca dados dos sensores.
   * AGORA: simula variações de ±2cm a cada chamada (FS-002..012) e lê o FS-001 real.
   */
  async fetchIoTData() {
    /* ─────────────────────────────────────────────────────────────
       INTEGRAÇÃO REAL — DESCOMENTAR QUANDO A API ESTIVER PRONTA

    try {
      const response = await fetch('http://localhost:3000/api/sensors', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          // 'Authorization': 'Bearer SEU_TOKEN_JWT'
        }
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      return data;

    } catch (error) {
      console.error('[FloodSense] Erro ao buscar dados da API:', error);
      return this.state.sensors;
    }

    ─────────────────────────────────────────────────────────────── */

    /* ── MODO SIMULAÇÃO (sensores sem hardware: FS-002..FS-012) ─────── */
    const simulados = this.state.sensors.map(s => {
      if (s.id === FIREBASE_SENSOR_ID) return s;   // FS-001 nunca é simulado
      if (s.status === 'offline') return s;

      // Variação aleatória de ±2 cm
      const delta = (Math.random() - 0.45) * 4;
      const newLevel = Math.max(5, Math.min(130, parseFloat((s.level + delta).toFixed(1))));

      // Recalcula status com base no nível
      let newStatus = 'normal';
      if (newLevel >= 90) newStatus = 'critical';
      else if (newLevel >= 60) newStatus = 'warning';

      // Temperatura: ±0.3°C
      const newTemp = s.temp == null ? null : parseFloat((s.temp + (Math.random() - 0.5) * 0.6).toFixed(1));

      const now = new Date();
      const hh  = String(now.getHours()).padStart(2, '0');
      const mm  = String(now.getMinutes()).padStart(2, '0');
      const ss  = String(now.getSeconds()).padStart(2, '0');

      return { ...s, level: newLevel, temp: newTemp, status: newStatus, lastRead: `${hh}:${mm}:${ss}` };
    });

    /* ── FS-001: leitura oficial de /sensors/FS-001.json ──
       Atualiza state.realSensorReading (única fonte do nível atual).
       Sem leitura válida → FS-001 offline, sem nível. */
    const reading = await this.fetchCurrentRealSensor();
    this.setRealPanel(reading);

    if (!reading) {
      return simulados.map(s => s.id === FIREBASE_SENSOR_ID ? fs001Offline(s) : s);
    }

    const now = new Date();
    const hhmmss = [now.getHours(), now.getMinutes(), now.getSeconds()].map(n => String(n).padStart(2, '0')).join(':');

    return simulados.map(s => s.id !== FIREBASE_SENSOR_ID ? s : {
      ...s, level: reading.level, status: reading.status, source: 'real', temp: null, humidity: null, lastRead: hhmmss   // AJ-SR04M não mede temp./umidade
    });
  },

  /** Inicia o polling de dados IoT (SENSOR_POLL_MS = 3 s) */
  startIoTSimulation() {
    clearInterval(this.state.iotInterval);
    const tick = async () => {
      const updated = await this.fetchIoTData();
      if (!this.state.loggedIn) return;
      this.state.sensors = updated;
      this.onIoTUpdate();
    };

    tick();
    this.state.iotInterval = setInterval(tick, SENSOR_POLL_MS);
  },

  /**
   * Callback chamado após cada atualização dos dados IoT.
   * Atualiza apenas os elementos da UI que mudaram.
   */
  onIoTUpdate() {
    const s = this.state.sensors;

    const online = s.filter(x => x.status !== 'offline').length;
    const elem   = document.getElementById('online-count');
    if (elem) elem.textContent = online;

    const navCount = document.getElementById('nav-count-sensors');
    if (navCount) navCount.textContent = s.length;

    const alertCount = (FloodSense.state.alerts || []).filter(a => a.type === 'critical' || a.type === 'warning').length;
    const navAlerts  = document.getElementById('nav-count-alerts');
    if (navAlerts) navAlerts.textContent = alertCount;

    // Barra do topo: só o sensor REAL (FS-001). Sensores simulados não disparam alarme aqui.
    const criticals = s.filter(x => x.status === 'critical' && x.source === 'real');
    const critBar   = document.getElementById('critical-bar');
    const critText  = document.getElementById('critical-bar-text');
    if (critBar && critText) {
      if (criticals.length > 0) {
        critBar.classList.remove('hidden');
        const c0 = criticals[0];
        critText.textContent = `${c0.name}: CRÍTICO ${c0.level}cm · REAL`;
      } else {
        critBar.classList.add('hidden');
      }
    }

    if (this.state.currentScreen === 'dashboard') {
      this.updateDashboardKPIs();
      this.updateDashboardChart();
      this.updateDashboardAICard();
    }

    if (this.state.currentScreen === 'sensors') {
      this.renderSensorTable();
    }

    if (this.state.currentScreen === 'ai') this.updateAIScreen();

    if (this.state.currentScreen === 'map' && this.state.leafletMap) {
      this.updateMapMarkers();
    }
  },

  /* ═════════════════════════════════════════════
     06. NAVEGAÇÃO
  ═════════════════════════════════════════════ */

  /**
   * Navega para uma tela.
   * @param {string} screenName — 'dashboard' | 'sensors' | 'map' |
   *                               'ai' | 'charts' | 'alerts' | 'reports' | 'config'
   */
  navigate(screenName) {
    clearInterval(this.state.aiInterval);
    this.state.aiInterval = null;
    const realPanel = document.getElementById('real-sensor-panel');
    if (realPanel) realPanel.style.display = screenName === 'dashboard' ? '' : 'none';
    if (this.state.leafletMap) {
      this.state.leafletMap.remove();
      this.state.leafletMap = null;
    }

    this.state.currentScreen = screenName;

    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.screen === screenName);
    });

    const titles = {
      dashboard: ['Dashboard Principal', 'São Paulo · SP · Brasil — Atualização automática'],

      sensors:  ['Sensores IoT', '12 sensores cadastrados · Atualização automática'],

      map:      ['Mapa Interativo', 'Localização georreferenciada dos sensores — OpenStreetMap'],

      ai:       ['IA & Previsões', 'Previsão de +60 min do FS-001 via Firebase'],

      charts:   ['Análise Gráfica', 'Histórico de níveis · Dados reais e dados simulados identificados'],

      alerts:   ['Central de Alertas', 'Monitoramento de ocorrências · Sensores em atenção e situação crítica'],

      reports:  ['Relatórios', 'Dados dos sensores · Histórico e informações do sistema'],

      config:   ['Configurações', 'Parâmetros do sistema, sensores e alertas']
    };

    const [title, sub] = titles[screenName] || ['FloodSense AI', ''];
    const titleEl = document.getElementById('page-title');
    const subEl   = document.getElementById('page-subtitle');
    if (titleEl) titleEl.textContent = title;
    if (subEl)   subEl.textContent   = sub;

    this.renderScreen(screenName);

    this.closeSidebar();
  },

  /** Limpa o #app-root e renderiza a tela correspondente. */
  renderScreen(screenName) {
    const root = document.getElementById('app-root');
    if (!root) return;

    root.innerHTML = '';
    root.style.animation = 'none';
    root.offsetHeight; // reflow
    root.style.animation = '';

    Object.keys(this.state.chartInstances).forEach(id => this.destroyChart(id));

    const screens = {
      dashboard: () => this.renderDashboard(),
      sensors:   () => this.renderSensors(),
      map:       () => this.renderMap(),
      ai:        () => this.renderAI(),
      charts:    () => this.renderCharts(),
      alerts:    () => this.renderAlerts(),
      reports:   () => this.renderReports(),
      config:    () => this.renderConfig()
    };

    if (screens[screenName]) {
      screens[screenName]();
    } else {
      root.innerHTML = `<div style="text-align:center;padding:60px;color:var(--text-muted)">
        <p style="font-size:48px;margin-bottom:12px">🚧</p>
        <p>Tela <strong style="color:var(--blue)">${screenName}</strong> em desenvolvimento.</p>
      </div>`;
    }

    FloodSense.icons();
  },

  /* ═════════════════════════════════════════════
     07. TELA: DASHBOARD
   ═════════════════════════════════════════════ */

  renderDashboard() {
    const root = document.getElementById('app-root');

    root.innerHTML = `

      <!-- Pedido manual de alerta para o celular (Telegram) -->
      <div class="content-card" style="margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">
        <div>
          <div class="content-card-title"><i data-lucide="bell-ring"></i> Alerta para o celular</div>
          <div class="chart-meta">Envia no Telegram uma mensagem com o nível atual do FS-001.</div>
        </div>
        <button class="btn btn-primary" id="btn-alerta-telegram" onclick="FloodSense.pedirAlertaTelegram()">
          <i data-lucide="send"></i> Enviar alerta
        </button>
      </div>

      <!-- KPIs -->
      <div class="kpi-grid" id="kpi-grid"></div>

      <!-- IA · Previsão do FS-001 (dados reais do Firebase) -->
      <div class="content-card" id="dash-ai-card" style="margin-bottom:12px">
        <div class="content-card-header">
          <span class="content-card-title">
            <i data-lucide="brain"></i>
            IA · Previsão +60 min — FS-001
          </span>
          <span class="chart-meta" id="dash-ai-note">consultando...</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px">
          ${[
            ['Nível atual', 'dash-ai-current'],
            ['Previsão +60 min', 'dash-ai-pred'],
            ['Status previsto', 'dash-ai-status'],
            ['Horário da previsão (São Paulo)', 'dash-ai-time']
          ].map(([label, id]) => `
            <div style="padding:12px;background:var(--bg-card-2);border:1px solid var(--border);border-radius:var(--radius-sm)">
              <span style="display:block;font-size:10px;color:var(--text-muted)">${label}</span>
              <strong id="${id}" style="display:block;margin-top:4px;font-size:18px;font-family:var(--text-mono)">—</strong>
            </div>
          `).join('')}
        </div>
        <p id="dash-ai-msg" style="font-size:11px;color:var(--yellow);margin-top:10px;line-height:1.6">Consultando previsão da IA...</p>
      </div>

      <!-- Gráficos principais -->
      <div class="grid-2" style="margin-bottom:12px">

        <div class="chart-card" style="animation-delay:0.1s">
          <div class="chart-header">
            <span class="chart-title">
              <i data-lucide="trending-up"></i>
              Nível da Água — 24h (simulado) + FS-001 real
            </span>
            <span class="chart-meta" id="chart-update">atualização automática</span>
          </div>

          <div class="chart-wrap" style="height:190px">
            <canvas id="chart-line"></canvas>
          </div>

          <div class="legend-row">
            <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div>Centro (simulado)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#F28C00"></div>Zona Norte (simulado)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#00B8D9"></div>Média (sensores ativos)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#16a36a"></div>FS-001 (real)</div>
          </div>
        </div>

        <div class="chart-card" style="animation-delay:0.15s">
          <div class="chart-header">
            <span class="chart-title">
              <i data-lucide="bar-chart-3"></i>
              Alertas por Região · SIMULADO
            </span>
          </div>
          <div class="chart-wrap" style="height:190px">
            <canvas id="chart-bar"></canvas>
          </div>
        </div>

      </div>

      <!-- Linha inferior -->
      <div class="grid-3">

        <div class="chart-card" style="animation-delay:0.2s">
          <div class="chart-header">
            <span class="chart-title">
              <i data-lucide="pie-chart"></i>
              Distribuição de Risco
            </span>
          </div>
          <div class="chart-wrap" style="height:160px">
            <canvas id="chart-pie"></canvas>
          </div>
          <div class="legend-row" style="justify-content:center;margin-top:10px">
            <div class="legend-item"><div class="legend-dot" style="background:#16a36a"></div>Normal</div>
            <div class="legend-item"><div class="legend-dot" style="background:#F28C00"></div>Atenção</div>
            <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div>Crítico</div>
          </div>
        </div>

        <div class="chart-card" style="animation-delay:0.25s">
          <div class="chart-header">
            <span class="chart-title">
              <i data-lucide="radio"></i>
              Sensores Online/Offline
            </span>
          </div>
          <div class="chart-wrap" style="height:160px">
            <canvas id="chart-online"></canvas>
          </div>
        </div>

        <div class="content-card" style="animation-delay:0.3s;margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title">
              <i data-lucide="bell"></i>
              Alertas Recentes
            </span>
          </div>

          ${this.state.alerts.slice(0, 3).map(a => {
            const cls = a.type === 'critical' ? 'alert-critical' : a.type === 'warning' ? 'alert-warning' : 'alert-info';
            return `
              <div class="alert-item ${cls}" style="padding:10px 12px;margin-bottom:6px">
                <div style="font-size:16px">${a.icon}</div>
                <div class="alert-content">
                  <div class="alert-title" style="font-size:12px">${a.zone}</div>
                  <div class="alert-description" style="font-size:10px">${a.msg.substring(0, 70)}...</div>
                </div>
                <div class="alert-time">${a.time}</div>
              </div>
            `;
          }).join('')}
        </div>

      </div>

    `;

    this.updateDashboardKPIs();

    FloodSense.icons();

    this.initDashboardCharts();
    this.updateDashboardAICard();

  },

  /** Calcula e injeta os 6 KPIs */
  updateDashboardKPIs() {

    const s = this.state.sensors || [];

    const online  = s.filter(x => x.status !== 'offline');
    const offline = s.filter(x => x.status === 'offline');
    const crits   = s.filter(x => x.status === 'critical');
    const warns   = s.filter(x => x.status === 'warning');
    const alCrit  = (this.state.alerts || []).filter(a => a.type === 'critical').length;
    const alWarn  = (this.state.alerts || []).filter(a => a.type === 'warning').length;

    const simOn  = online.filter(x => x.source !== 'real');   // média e máximo: só SIMULADOS
    const avgLvl = simOn.length
      ? (simOn.reduce((total, x) => total + Number(x.level || 0), 0) / simOn.length).toFixed(1)
      : '0.0';

    const maxLvl = simOn.length
      ? Math.max(...simOn.map(x => Number(x.level || 0))).toFixed(1)
      : '0.0';

    const uptime = s.length ? Math.round((online.length / s.length) * 100) : 0;

    // Previsão da IA — SOMENTE dados reais do Firebase (/ai_predictions)
    const aiPred = this.state.aiPrediction || this.emptyPrediction('loading');
    const aiOk   = aiPred.available === true;
    const aiMeta = this.aiStatusMeta(aiPred.status);
    const aiCur  = this.getCurrentRealLevel();   // nível atual REAL (/sensors/FS-001)

    const kpis = [

      /* 1 — Sensores Online */
      {
        label: 'Sensores Online',
        value: online.length,
        sub: `${offline.length} offline`,
        type: 'blue',
        icon: 'radio',
        iconCls: 'ic-blue',
        valCls: 'col-blue',
        trend: `${uptime}% uptime`,
        trendType: 'flat'
      },

      /* 2 — Nível Médio */
      {
        label: 'Nível Médio H₂O',
        value: `${avgLvl}cm`,
        sub: `Máx: ${maxLvl}cm · média só de sensores SIMULADOS`,
        type:    Number(avgLvl) >= 90 ? 'red'      : Number(avgLvl) >= 60 ? 'yellow'      : 'green',
        icon: 'droplets',
        iconCls: Number(avgLvl) >= 90 ? 'ic-red'   : Number(avgLvl) >= 60 ? 'ic-yellow'   : 'ic-green',
        valCls:  Number(avgLvl) >= 90 ? 'col-red'  : Number(avgLvl) >= 60 ? 'col-yellow'  : 'col-green',
        trend:   Number(avgLvl) >= 60 ? '▲ Acima do normal' : '▼ Normal',
        trendType: Number(avgLvl) >= 60 ? 'up' : 'down'
      },

      /* 3 — Previsão da IA (+60 min) — valor real do Firebase ou "AGUARDANDO" */
      {
        label: 'Previsão IA +60 min',
        value: aiOk ? `${aiPred.predicted.toFixed(1)}cm` : 'AGUARDANDO',
        sub: aiOk ? `Atual: ${this.fmtCurrentLevel()} · ${aiPred.generatedLabel}` : this.aiWaitingText(aiPred),
        type: aiOk ? aiMeta.kpi : 'yellow',
        icon: 'brain',
        iconCls: aiOk ? aiMeta.ic : 'ic-yellow',
        valCls: aiOk ? aiMeta.val : 'col-yellow',
        trend: aiOk ? `● ${aiMeta.label}${aiPred.stale ? ' · desatualizada' : ''}` : '● Sem previsão disponível',
        trendType: aiOk && aiCur !== null && aiPred.predicted > aiCur ? 'up' : 'flat'
      },

      /* 4 — Alertas Ativos */
      {
        label: 'Alertas Ativos',
        value: alCrit + alWarn,
        sub: `${alCrit} críticos · ${alWarn} atenção`,
        type:    alCrit > 0 ? 'red'     : alWarn > 0 ? 'yellow'     : 'green',
        icon: 'bell',
        iconCls: alCrit > 0 ? 'ic-red'  : alWarn > 0 ? 'ic-yellow'  : 'ic-green',
        valCls:  alCrit > 0 ? 'col-red' : alWarn > 0 ? 'col-yellow' : 'col-green',
        trend:   alCrit > 0 ? '▲ Ação imediata' : alWarn > 0 ? '▲ Atenção' : '● Monitorando',
        trendType: alCrit > 0 ? 'up' : 'flat'
      },

      /* 5 — Áreas Monitoradas */
      {
        label: 'Áreas Monitoradas',
        value: '8',
        sub: 'Zonas cobertas',
        type: 'blue',
        icon: 'map-pin',
        iconCls: 'ic-blue',
        valCls: 'col-blue',
        trend: 'SP · Grande SP',
        trendType: 'flat'
      },

      /* 6 — Status da IA */
      {
        label: 'Status da IA',
        value: aiOk ? 'ATIVA' : (aiPred.reason === 'stale' ? 'DESATUALIZADA' : (aiPred.reason === 'error' ? 'FALHA' : 'AGUARDANDO')),
        sub: aiOk ? `${this.esc(this.aiModelLabel(aiPred) || 'Modelo')} · ${this.esc(aiPred.unit || 'cm')}` : this.aiWaitingText(aiPred),
        type: aiOk ? 'green' : (aiPred.reason === 'error' ? 'red' : 'yellow'),
        icon: 'cpu',
        iconCls: aiOk ? 'ic-green' : (aiPred.reason === 'error' ? 'ic-red' : 'ic-yellow'),
        valCls: aiOk ? 'col-green' : (aiPred.reason === 'error' ? 'col-red' : 'col-yellow'),
        trend: aiOk ? '● Previsão publicada' : '● Sem previsão disponível',
        trendType: 'flat'
      }

    ];

    const grid = document.getElementById('kpi-grid');

    if (!grid) return;

    grid.innerHTML = kpis.map((k, i) => `

      <div class="kpi-card kpi-${k.type}" style="animation-delay:${i * 0.05}s">

        <div class="kpi-header">
          <span class="kpi-label">${k.label}</span>
          <div class="kpi-icon ${k.iconCls}">
            <i data-lucide="${k.icon}"></i>
          </div>
        </div>

        <div class="kpi-value ${k.valCls}">${k.value}</div>

        <div class="kpi-sub">${k.sub}</div>

        <span class="kpi-trend trend-${k.trendType}">${k.trend}</span>

      </div>

    `).join('');

    FloodSense.icons();

  },

  /** Inicializa os 4 gráficos do dashboard */
  initDashboardCharts() {
    const d = this.chartDefaults();

    // Gráfico de linha — Nível 24h
    this.makeChart('chart-line', {
      type: 'line',
      data: {
        labels: [...HISTORY_24H.labels],
        datasets: [
          {
            label: 'Centro (simulado)', data: [...HISTORY_24H.centro],
            borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.06)',
            tension: 0.4, fill: true, borderWidth: 2, pointRadius: 0
          },
          {
            label: 'Norte', data: [...HISTORY_24H.norte],
            borderColor: '#F28C00', backgroundColor: 'rgba(242,140,0,0.04)',
            tension: 0.4, fill: true, borderWidth: 1.5, pointRadius: 0
          },
          {
            label: 'Média', data: [...HISTORY_24H.media],
            borderColor: '#00B8D9', backgroundColor: 'rgba(0,184,217,0.05)',
            tension: 0.4, fill: true, borderWidth: 2, pointRadius: 0
          },
          {
            label: 'FS-001 (real)', data: Array(24).fill(null),
            borderColor: '#16a36a', backgroundColor: 'transparent',
            tension: 0.3, fill: false, borderWidth: 2, borderDash: [5, 4], pointRadius: 3, spanGaps: false
          }
        ]
      },
      options: {
        ...d,
        scales: {
          x: { ...d.scales.x, ticks: { ...d.scales.x.ticks, maxTicksLimit: 8 } },
          y: { ...d.scales.y, ticks: { ...d.scales.y.ticks, callback: v => v + 'cm' }, suggestedMin: 0 }
        }
      }
    });

    // Gráfico de barras — Alertas por região
    this.makeChart('chart-bar', {
      type: 'bar',
      data: {
        labels: ['Centro', 'Z.Norte', 'Z.Sul', 'Z.Leste', 'Z.Oeste', 'Marginal', 'Penha', 'Jabaq.'],
        datasets: [{
          label: 'Alertas',
          data: [8, 6, 5, 3, 2, 4, 2, 1],
          backgroundColor: ['#ef4444','#ef4444','#F28C00','#F28C00','#16a36a','#F28C00','#16a36a','#16a36a'],
          borderRadius: 4,
          borderSkipped: false
        }]
      },
      options: { ...d }
    });

    // Gráfico de pizza — Distribuição de risco
    const counts = {
      normal:   this.state.sensors.filter(x => x.status === 'normal').length,
      warning:  this.state.sensors.filter(x => x.status === 'warning').length,
      critical: this.state.sensors.filter(x => x.status === 'critical').length
    };
    this.makeChart('chart-pie', {
      type: 'doughnut',
      data: {
        labels: ['Normal', 'Atenção', 'Crítico'],
        datasets: [{
          data: [counts.normal, counts.warning, counts.critical],
          backgroundColor: ['#16a36a', '#F28C00', '#ef4444'],
          borderColor: '#ffffff', borderWidth: 3, hoverOffset: 4
        }]
      },
      options: {
        ...d,
        cutout: '65%',
        plugins: { ...d.plugins, tooltip: { ...d.plugins.tooltip, callbacks: { label: c => ` ${c.label}: ${c.raw} sensores` } } }
      }
    });

    // Gráfico de barras horizontais — Online vs Offline
    this.makeChart('chart-online', {
      type: 'bar',
      data: {
        labels: ['Online', 'Offline'],
        datasets: [{
          data: [
            this.state.sensors.filter(x => x.status !== 'offline').length,
            this.state.sensors.filter(x => x.status === 'offline').length
          ],
          backgroundColor: ['rgba(22,163,106,0.7)', 'rgba(100,116,139,0.5)'],
          borderRadius: 6, borderSkipped: false
        }]
      },
      options: {
        ...d,
        indexAxis: 'y',
        scales: {
          x: { ...d.scales.x, max: 12, ticks: { ...d.scales.x.ticks, stepSize: 3 } },
          y: { ...d.scales.y, grid: { display: false } }
        }
      }
    });
  },

  /** Atualiza o gráfico de linha com o nível atual dos sensores */
  updateDashboardChart() {
    const chart = this.state.chartInstances['chart-line'];
    if (!chart) return;
    const label = `${String(new Date().getHours()).padStart(2, '0')}h`;
    if (chart.data.labels[chart.data.labels.length - 1] === label) return;

    const active = this.state.sensors.filter(x => x.status !== 'offline');
    const norte  = this.state.sensors.find(x => x.id === 'FS-002');
    const real   = this.state.sensors.find(x => x.source === 'real');
    const avg    = active.length
      ? parseFloat((active.reduce((a, x) => a + Number(x.level || 0), 0) / active.length).toFixed(1))
      : null;

    chart.data.labels.push(label);
    chart.data.datasets[0].data.push(null);
    chart.data.datasets[1].data.push(norte && norte.status !== 'offline' ? norte.level : null);
    chart.data.datasets[2].data.push(avg);
    chart.data.datasets[3].data.push(real ? real.level : null);
    if (chart.data.labels.length > 24) {
      chart.data.labels.shift();
      chart.data.datasets.forEach(ds => ds.data.shift());
    }
    chart.update('none');
  },

  /* ═════════════════════════════════════════════
     08. TELA: SENSORES
  ═════════════════════════════════════════════ */
  renderSensors() {
    const root = document.getElementById('app-root');
    root.innerHTML = `
      <div class="table-container">
        <div class="table-toolbar">
          <div class="table-search">
            <i data-lucide="search"></i>
            <input
              id="sensor-search"
              type="text"
              placeholder="Buscar por ID, nome, bairro..."
              oninput="FloodSense.onSensorSearch(this.value)"
              value="${this.state.searchQuery}"
            />
          </div>
          <div class="filter-group">
            <button class="filter-btn ${this.state.filterStatus==='all'?'active':''}"      onclick="FloodSense.setSensorFilter('all')">Todos</button>
            <button class="filter-btn ${this.state.filterStatus==='normal'?'active':''}"   onclick="FloodSense.setSensorFilter('normal')">Normal</button>
            <button class="filter-btn ${this.state.filterStatus==='warning'?'active':''}"  onclick="FloodSense.setSensorFilter('warning')">Atenção</button>
            <button class="filter-btn ${this.state.filterStatus==='critical'?'active':''}" onclick="FloodSense.setSensorFilter('critical')">Crítico</button>
            <button class="filter-btn ${this.state.filterStatus==='offline'?'active':''}"  onclick="FloodSense.setSensorFilter('offline')">Offline</button>
          </div>
          <span class="table-count" id="sensor-count"></span>
        </div>
        <div style="overflow-x:auto">
          <table class="sensor-table">
            <thead>
              <tr>
                <th onclick="FloodSense.sortSensors('id')">ID</th>
                <th onclick="FloodSense.sortSensors('name')">Nome</th>
                <th onclick="FloodSense.sortSensors('bairro')">Bairro</th>
                <th onclick="FloodSense.sortSensors('level')">Nível H₂O ↕</th>
                <th onclick="FloodSense.sortSensors('temp')">Temp.</th>
                <th>Umidade</th>
                <th onclick="FloodSense.sortSensors('status')">Status</th>
                <th>Última Leitura</th>
              </tr>
            </thead>
            <tbody id="sensor-tbody"></tbody>
          </table>
        </div>
        <div class="pagination" id="sensor-pagination"></div>
      </div>
    `;
    FloodSense.icons();
    this.renderSensorTable();
  },

  /** Filtra, ordena e renderiza as linhas da tabela */
  renderSensorTable() {
    let data = [...this.state.sensors];

    if (this.state.searchQuery) {
      const q = this.state.searchQuery.toLowerCase();
      data = data.filter(s =>
        s.id.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.bairro.toLowerCase().includes(q) ||
        s.location.toLowerCase().includes(q)
      );
    }

    if (this.state.filterStatus !== 'all') {
      data = data.filter(s => s.status === this.state.filterStatus);
    }

    data.sort((a, b) => {
      let va = a[this.state.sortField], vb = b[this.state.sortField];
      if (typeof va === 'string') va = va.toLowerCase(), vb = vb.toLowerCase();
      if (va < vb) return this.state.sortDir === 'asc' ? -1 :  1;
      if (va > vb) return this.state.sortDir === 'asc' ?  1 : -1;
      return 0;
    });

    const total   = data.length;
    const pages   = Math.ceil(total / this.state.rowsPerPage);
    const start   = (this.state.currentPage - 1) * this.state.rowsPerPage;
    const pageData = data.slice(start, start + this.state.rowsPerPage);

    const countEl = document.getElementById('sensor-count');
    if (countEl) countEl.textContent = `${total} sensor${total !== 1 ? 'es' : ''}`;

    const tbody = document.getElementById('sensor-tbody');
    if (!tbody) return;
    tbody.innerHTML = pageData.map(s => `
      <tr>
        <td><span class="sensor-id">${s.id}</span>${this.getSourceTag(s)}</td>
        <td><span class="sensor-name">${s.name}</span></td>
        <td style="color:var(--text-secondary)">${s.bairro}</td>
        <td>
          <span class="sensor-level ${this.getLevelClass(s.status)}">
            ${s.status === 'offline' ? (s.id === FIREBASE_SENSOR_ID ? 'Sem leitura' : '—') : s.level + ' cm'}
          </span>
        </td>
        <td style="font-family:var(--text-mono)">${s.status === 'offline' ? '—' : this.fmtVal(s.temp, '°C')}</td>
        <td style="font-family:var(--text-mono)">${s.status === 'offline' ? '—' : this.fmtVal(s.humidity, '%')}</td>
        <td>${this.getStatusBadge(s.status)}</td>
        <td style="font-family:var(--text-mono);font-size:11px;color:var(--text-muted)">${s.lastRead}</td>
      </tr>
    `).join('');

    const pgEl = document.getElementById('sensor-pagination');
    if (!pgEl) return;
    pgEl.innerHTML = `
      <span>${total === 0 ? 0 : start + 1}–${Math.min(start + this.state.rowsPerPage, total)} de ${total}</span>
      <div class="pagination-btns">
        <button class="pg-btn" onclick="FloodSense.goPage(${this.state.currentPage - 1})" ${this.state.currentPage <= 1 ? 'disabled' : ''}>‹ Ant.</button>
        ${Array.from({ length: pages }, (_, i) => `
          <button class="pg-btn ${i + 1 === this.state.currentPage ? 'active' : ''}" onclick="FloodSense.goPage(${i + 1})">${i + 1}</button>
        `).join('')}
        <button class="pg-btn" onclick="FloodSense.goPage(${this.state.currentPage + 1})" ${this.state.currentPage >= pages ? 'disabled' : ''}>Próx. ›</button>
      </div>
    `;
  },

  onSensorSearch(val)        { this.state.searchQuery = val; this.state.currentPage = 1; this.renderSensorTable(); },
  setSensorFilter(status)    { this.state.filterStatus = status; this.state.currentPage = 1; this.navigate('sensors'); },
  goPage(p)                  { this.state.currentPage = p; this.renderSensorTable(); },
  sortSensors(field) {
    if (this.state.sortField === field) this.state.sortDir = this.state.sortDir === 'asc' ? 'desc' : 'asc';
    else { this.state.sortField = field; this.state.sortDir = 'asc'; }
    this.renderSensorTable();
  },

  /* ═════════════════════════════════════════════
     09. TELA: MAPA INTERATIVO (Leaflet)
  ═════════════════════════════════════════════ */
  renderMap() {
    const root = document.getElementById('app-root');
    root.innerHTML = `
      <div class="grid-3" style="margin-bottom:12px">
        ${[
          { label:'Sensores Online', val: this.state.sensors.filter(x=>x.status!=='offline').length + '/12', color:'var(--green)' },
          { label:'Zonas Críticas',  val: this.state.sensors.filter(x=>x.status==='critical').length,         color:'var(--red)' },
          { label:'Zonas Atenção',   val: this.state.sensors.filter(x=>x.status==='warning').length,          color:'var(--yellow)' }
        ].map((k,i) => `
          <div class="content-card" style="margin-bottom:0;text-align:center;animation-delay:${i*0.06}s;padding:12px">
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">${k.label}</div>
            <div style="font-size:26px;font-weight:700;color:${k.color};font-family:var(--text-mono)">${k.val}</div>
          </div>
        `).join('')}
      </div>

      <div class="map-full-card">
        <div class="map-full-header">
          <span class="content-card-title" style="font-size:13px;font-weight:700;display:flex;align-items:center;gap:8px">
            <i data-lucide="map" style="width:15px;height:15px;color:var(--blue)"></i>
            São Paulo — Sensores (FS-001 real · demais simulados)
          </span>
          <div style="display:flex;gap:6px">
            <span class="badge badge-green">● ${this.state.sensors.filter(x=>x.status==='normal').length} Normal</span>
            <span class="badge badge-yellow">● ${this.state.sensors.filter(x=>x.status==='warning').length} Atenção</span>
            <span class="badge badge-red">● ${this.state.sensors.filter(x=>x.status==='critical').length} Crítico</span>
          </div>
        </div>
        <div class="map-full-body">
          <div id="leaflet-map"></div>
          <!-- Legenda sobreposta ao mapa -->
          <div class="map-legend-card">
            <div class="map-legend-title">Legenda</div>
            <div class="map-legend-item"><div class="map-legend-dot" style="background:var(--green)"></div>Normal (&lt;60cm)</div>
            <div class="map-legend-item"><div class="map-legend-dot" style="background:var(--yellow)"></div>Atenção (60–90cm)</div>
            <div class="map-legend-item"><div class="map-legend-dot" style="background:var(--red)"></div>Crítico (&gt;90cm)</div>
            <div class="map-legend-item"><div class="map-legend-dot" style="background:var(--text-muted)"></div>Offline</div>
          </div>
        </div>
      </div>
    `;
    FloodSense.icons();

    setTimeout(() => this.initLeafletMap(), 100);
  },

  /** Inicializa o mapa Leaflet com marcadores */
  initLeafletMap() {
    if (!document.getElementById('leaflet-map') || this.state.currentScreen !== 'map') return;
    if (!window.L) {
      document.getElementById('leaflet-map').innerHTML =
        '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">Leaflet não carregado. Verifique sua conexão.</div>';
      return;
    }

    /* Evita inicializar o Leaflet duas vezes no mesmo container
       (ex.: navegar para o mapa repetidamente em menos de 100 ms). */
    const mapEl = document.getElementById('leaflet-map');
    if (this.state.leafletMap) {
      if (this.state.leafletMap.getContainer() === mapEl) {
        this.state.leafletMap.invalidateSize();
        return;
      }
      this.state.leafletMap.remove();
      this.state.leafletMap = null;
    }

    const map = L.map('leaflet-map', {
      center: [FS001_COORDS.lat, FS001_COORDS.lng],   // região da faculdade (fixo)
      zoom: MAP_INITIAL_ZOOM,
      zoomControl: true,
      attributionControl: true
    });

    // Mapa base: Esri World Street Map (visual de mapa de ruas, sem chave de API)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Tiles &copy; <a href="https://www.esri.com/" target="_blank" rel="noopener noreferrer">Esri</a> — Fontes: Esri, HERE, Garmin, OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(map);

    this.state.leafletMap = map;
    this.state.leafletMarkers = [];

    /* Redimensionamento: recalcula o tamanho assim que o container estiver
       visível e sempre que ele mudar de tamanho (troca de tela, sidebar, rotação). */
    const refreshSize = () => { if (this.state.leafletMap === map) map.invalidateSize(); };
    requestAnimationFrame(refreshSize);
    setTimeout(refreshSize, 250);
    if (window.ResizeObserver) {
      const ro = new ResizeObserver(refreshSize);
      ro.observe(mapEl);
      map.on('unload', () => ro.disconnect());
    }

    this.state.sensors.forEach(s => {
      const color = s.status === 'critical' ? '#ef4444' :
                    s.status === 'warning'  ? '#F28C00' :
                    s.status === 'offline'  ? '#475569' : '#22c55e';

      const icon = L.divIcon({
        className: '',
        html: `<div style="
          width:16px;height:16px;border-radius:50%;
          background:${color};
          border:2px solid rgba(255,255,255,0.6);
          box-shadow:0 0 10px ${color}55;
          ${s.status === 'critical' ? 'animation:pulse-ring 1.5s ease infinite' : ''};
        "></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8],
        popupAnchor: [0, -12]
      });

      const marker = L.marker([s.lat, s.lng], { icon })
        .bindPopup(this.buildMapPopup(s), {
          className: 'custom-leaflet-popup',
          maxWidth: 240,
          minWidth: 220
        })
        .addTo(map);

      this.state.leafletMarkers.push({ sensor: s, marker });
    });
  },

  /** Constrói HTML do popup do mapa */
  buildMapPopup(s) {
    const statusColor = s.status === 'critical' ? 'var(--red)' :
                        s.status === 'warning'  ? 'var(--yellow)' :
                        s.status === 'offline'  ? 'var(--text-muted)' : 'var(--green)';
    return `<div class="map-popup">
      <div class="map-popup-title">${s.name} ${this.getSourceTag(s)}</div>
      <div class="map-popup-row"><span>📍 Local</span><span>${s.bairro}</span></div>
      <div class="map-popup-row"><span>💧 Nível</span><span style="color:${statusColor}">${s.status==='offline'?(s.id===FIREBASE_SENSOR_ID?'Sem leitura':'—'):s.level+' cm'}</span></div>
      <div class="map-popup-row"><span>🌡️ Temp.</span><span>${s.status==='offline'?'—':this.fmtVal(s.temp,'°C')}</span></div>
      <div class="map-popup-row"><span>💦 Umidade</span><span>${s.status==='offline'?'—':this.fmtVal(s.humidity,'%')}</span></div>
      <div class="map-popup-row"><span>🕐 Leitura</span><span>${s.lastRead}</span></div>
      <div style="margin-top:8px;padding-top:8px;border-top:1px solid #e1eaee">
        ${this.getStatusBadge(s.status)}
      </div>
    </div>`;
  },

  /** Atualiza popups dos marcadores com novos dados */
  updateMapMarkers() {
    if (!this.state.leafletMarkers) return;
    this.state.leafletMarkers.forEach(({ sensor, marker }) => {
      const updated = this.state.sensors.find(s => s.id === sensor.id);
      if (updated) {
        marker.setPopupContent(this.buildMapPopup(updated));
      }
    });
  },

  /* ═════════════════════════════════════════════
     10. TELA: IA & PREVISÕES
     Responsabilidades separadas (nenhum valor simulado):
       • /sensors/FS-001.json                    → NÍVEL ATUAL REAL
       • /ai_predictions/FS-001.json             → previsão +60 min
       • /sensor_history_treinamento/FS-001.json → histórico real (gráfico)
  ═════════════════════════════════════════════ */

  renderAI() {
    const root = document.getElementById('app-root');

    if (!root) return;

    clearInterval(this.state.aiInterval);
    this.state.aiInterval = null;

    const infoRow = (label, valueHtml, last = false) => `
      <div style="display:flex;justify-content:space-between;gap:12px;${last ? '' : 'border-bottom:1px solid var(--border-3);padding-bottom:8px;'}">
        <span style="color:var(--text-muted)">${label}</span>
        ${valueHtml}
      </div>`;

    const pipeStep = (icon, color, text, iconId = '', textId = '') => `
      <div style="display:flex;align-items:center;gap:9px">
        <span style="color:${color}" ${iconId ? `id="${iconId}"` : ''}>${icon}</span>
        <span ${textId ? `id="${textId}"` : ''}>${text}</span>
      </div>`;

    root.innerHTML = `

      <!-- IA & PREVISÕES — DADOS REAIS DO PROTÓTIPO -->

      <div class="kpi-grid" style="margin-bottom:12px">

        <!-- NÍVEL ATUAL -->
        <div class="kpi-card kpi-blue">
          <div class="kpi-header">
            <span class="kpi-label">NÍVEL ATUAL — FS-001</span>
            <div class="kpi-icon ic-blue"><i data-lucide="droplets"></i></div>
          </div>
          <div class="kpi-value col-blue" id="ai-current-level">—</div>
          <div class="kpi-sub">Sensor real · cm</div>
          <span class="kpi-trend trend-flat" id="ai-current-status">aguardando Firebase</span>
        </div>

        <!-- HISTÓRICO -->
        <div class="kpi-card kpi-blue">
          <div class="kpi-header">
            <span class="kpi-label">HISTÓRICO DISPONÍVEL</span>
            <div class="kpi-icon ic-blue"><i data-lucide="database"></i></div>
          </div>
          <div class="kpi-value col-blue" id="ai-history-count">—</div>
          <div class="kpi-sub">Leituras do FS-001</div>
          <span class="kpi-trend trend-flat">Amostragem a cada 5 min</span>
        </div>

        <!-- PREVISÃO -->
        <div class="kpi-card kpi-yellow">
          <div class="kpi-header">
            <span class="kpi-label">PREVISÃO — 60 MIN</span>
            <div class="kpi-icon ic-yellow"><i data-lucide="brain"></i></div>
          </div>
          <div class="kpi-value col-yellow" id="ai-prediction-value">—</div>
          <div class="kpi-sub" id="ai-prediction-status">Aguardando previsão da IA</div>
          <span class="kpi-trend trend-flat" id="ai-prediction-time">Aguardando previsão da IA</span>
        </div>

        <!-- COMPATIBILIDADE -->
        <div class="kpi-card kpi-yellow">
          <div class="kpi-header">
            <span class="kpi-label">COMPATIBILIDADE</span>
            <div class="kpi-icon ic-yellow"><i data-lucide="shield-check"></i></div>
          </div>
          <div class="kpi-value col-yellow" id="ai-compatibility">AGUARDANDO</div>
          <div class="kpi-sub">Modelo atual × sensor real</div>
          <span class="kpi-trend trend-flat" id="ai-compat-note">Sem previsão publicada</span>
        </div>

      </div>


      <!-- GRÁFICO + ESTADO DA IA -->

      <div class="grid-2" style="margin-bottom:12px">

        <!-- HISTÓRICO REAL -->
        <div class="chart-card">
          <div class="chart-header">
            <span class="chart-title">
              <i data-lucide="activity"></i>
              Histórico real — FS-001 <span class="data-tag data-tag-real">REAL</span>
            </span>
            <span class="chart-meta" id="ai-chart-meta">Firebase · carregando...</span>
          </div>

          <div class="chart-wrap" style="height:240px">
            <canvas id="chart-ai-pred"></canvas>
          </div>

          <div class="legend-row">
            <div class="legend-item">
              <div class="legend-dot" style="background:#00B8D9"></div>
              Nível real do ESP32
            </div>
            <div class="legend-item" style="color:var(--text-muted)">
              Leituras de /sensor_history_treinamento · atualização automática
            </div>
          </div>
        </div>


        <!-- ESTADO DA IA -->
        <div class="content-card" style="margin-bottom:0">

          <div class="content-card-header">
            <span class="content-card-title">
              <i data-lucide="brain"></i>
              Estado da Inteligência Artificial
            </span>
          </div>

          <div id="ai-status-box" style="background:rgba(242,140,0,0.06);border:1px solid rgba(242,140,0,0.22);border-radius:var(--radius-md);padding:16px;margin-bottom:16px">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
              <span style="width:10px;height:10px;border-radius:50%;background:var(--yellow);display:inline-block"></span>
              <strong style="color:var(--yellow)" id="ai-status-title">Aguardando previsão da IA</strong>
            </div>
            <p id="ai-status-message" style="font-size:12px;color:var(--text-secondary);line-height:1.6">
              Consultando /ai_predictions/${FIREBASE_SENSOR_ID} no Firebase...
            </p>
          </div>

          <!-- INFORMAÇÕES DO MODELO -->
          <div style="font-size:12px;display:flex;flex-direction:column;gap:10px">
            ${infoRow('Sensor real', '<strong style="color:var(--text-secondary)">ESP32 + AJ-SR04M</strong>')}
            ${infoRow('Unidade do sensor', '<strong style="color:var(--blue)">cm</strong>')}
            ${infoRow('Modelo atual', '<strong style="color:var(--text-secondary)" id="ai-info-model">—</strong>')}
            ${infoRow('Unidade da previsão', '<strong style="color:var(--yellow)" id="ai-info-unit">—</strong>')}
            ${infoRow('Horizonte configurado', '<strong style="color:var(--text-secondary)" id="ai-info-horizon">60 min</strong>', true)}
          </div>

        </div>

      </div>


      <!-- MODELO V4 + PIPELINE -->

      <div class="grid-2">

        <!-- MODELO V4 PROGRESSIVO (dados reais publicados pelo Python) -->
        <div class="content-card" style="margin-bottom:0">

          <div class="content-card-header">
            <span class="content-card-title">
              <i data-lucide="brain"></i>
              FloodSense AI — V4 Progressivo
            </span>
          </div>

          <div style="font-size:12px;display:flex;flex-direction:column;gap:10px">
            ${infoRow('Algoritmo', '<strong style="color:var(--text-secondary)" id="ai-v4-algo">—</strong>')}
            ${infoRow('Modo', '<strong style="color:var(--blue)" id="ai-v4-mode">—</strong>')}
            ${infoRow('Lags usados', '<strong style="color:var(--text-secondary)" id="ai-v4-lags">—</strong>')}
            ${infoRow('Versão do modelo', '<strong style="color:var(--text-secondary)" id="ai-v4-version">—</strong>')}
            ${infoRow('MAE de teste (modelo escolhido)', '<strong style="color:var(--text-secondary)" id="ai-v4-mae">—</strong>', true)}
          </div>

        </div>


        <!-- PIPELINE -->
        <div class="content-card" style="margin-bottom:0">

          <div class="content-card-header">
            <span class="content-card-title">
              <i data-lucide="route"></i>
              Pipeline da IA
            </span>
          </div>

          <div style="display:flex;flex-direction:column;gap:9px;font-size:11px">
            ${pipeStep('✓', 'var(--green)', 'ESP32 realiza a leitura do nível')}
            ${pipeStep('✓', 'var(--green)', 'Firebase armazena o sensor e o histórico')}
            ${pipeStep('✓', 'var(--green)', 'Python consulta o histórico em /sensor_history_treinamento')}
            ${pipeStep('✓', 'var(--green)', 'Modelo V4 escolhe STARTUP, LAG_5, LAG_15 ou FULL conforme as leituras reais')}
            ${pipeStep('●', 'var(--yellow)', 'Aguardando o Python publicar a previsão em /ai_predictions', 'ai-pipe-icon', 'ai-pipe-text')}
          </div>

        </div>

      </div>

    `;

    FloodSense.icons();

    this.initAICharts();

    this.loadAIData();

    // Atualização automática
    this.state.aiInterval = setInterval(() => {
      if (this.state.currentScreen === 'ai') {
        this.loadAIData();
      }
    }, AI_POLL_MS);
  },


  /* ═════════════════════════════════════════════
     CARREGAR DADOS REAIS DA IA
     - Nível atual: this.state.realSensorReading (polling de 3 s, seção 05)
     - Previsão: fetchAIPrediction() (seção 03b) → updateAIScreen()
     - Histórico: loadAIHistory() abaixo
     As consultas são independentes.
  ═════════════════════════════════════════════ */

  async loadAIData() {
    this.updateAIScreen();
    await Promise.all([
      this.fetchAIPrediction(),
      this.loadAIHistory()
    ]);
  },

  /** Histórico real (/sensor_history_treinamento/FS-001.json) → gráfico da tela de IA */
  async loadAIHistory() {
    if (!FIREBASE_HOST || !FIREBASE_SENSOR_ID) return;

    let historyData = null;
    try {
      const url = `https://${FIREBASE_HOST}/sensor_history_treinamento/${FIREBASE_SENSOR_ID}.json`;
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`Histórico HTTP ${response.status}`);
      historyData = await response.json();
    } catch (error) {
      console.warn('[FloodSense] Erro ao carregar histórico da IA:', error);
      this.setText('ai-chart-meta', 'histórico indisponível');
      return;
    }

    if (this.state.currentScreen !== 'ai') return;

    const history = this.parseHistory(historyData);

    // Mostra no máximo as 30 leituras mais recentes.
    const recent = history.slice(-30);

    const labels = recent.map((item, i) => {
      const ms = item.timestamp > 1e12 ? item.timestamp : item.timestamp * 1000;
      if (item.timestamp < 1e9) return `#${i + 1}`;   // timestamp não é epoch
      return new Date(ms).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' });
    });
    const levels = recent.map(item => Number(item.level.toFixed(1)));

    const chart = this.state.chartInstances['chart-ai-pred'];
    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = levels;
      chart.update('none');
    }

    this.setText('ai-history-count', String(history.length));
    this.setText('ai-chart-meta', recent.length ? `${recent.length} leituras reais · Firebase` : 'sem leituras no histórico');
  },


  /* ═════════════════════════════════════════════
     GRÁFICO DA IA
   ═════════════════════════════════════════════ */

  initAICharts() {

    const d = this.chartDefaults();

    this.makeChart('chart-ai-pred', {
      type: 'line',

      data: {
        labels: [],

        datasets: [
          {
            label: 'Nível real FS-001',
            data: [],
            borderColor: '#00B8D9',
            backgroundColor: 'rgba(0,184,217,0.08)',
            tension: 0.35,
            fill: true,
            borderWidth: 2,
            pointRadius: 2,
            pointBackgroundColor: '#00B8D9'
          }
        ]
      },

      options: {
        ...d,
        plugins: { ...d.plugins, legend: { display: false } },
        scales: {
          x: { ...d.scales.x, ticks: { ...d.scales.x.ticks, maxTicksLimit: 8 } },
          y: { ...d.scales.y, ticks: { ...d.scales.y.ticks, callback: value => value + ' cm' } }
        }
      }
    });

  },

  /* ═════════════════════════════════════════════
     11. TELA: ANÁLISE GRÁFICA
  ═════════════════════════════════════════════ */
  renderCharts() {
    const root = document.getElementById('app-root');
    const ai = this.aiSummary();
    root.innerHTML = `
      <div class="grid-2" style="margin-bottom:12px">
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title"><i data-lucide="trending-up"></i> Nível médio — 7 dias · SIMULADO</span></div>
          <div class="chart-wrap" style="height:200px"><canvas id="chart-week"></canvas></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title"><i data-lucide="cloud-rain"></i> Precipitação vs Nível · SIMULADO</span></div>
          <div class="chart-wrap" style="height:200px"><canvas id="chart-rain"></canvas></div>
        </div>
      </div>
      <div class="grid-2">
        <div class="chart-card" style="animation-delay:0.1s">
          <div class="chart-header"><span class="chart-title"><i data-lucide="bar-chart-3"></i> Alertas por zona — Mês · SIMULADO</span></div>
          <div class="chart-wrap" style="height:200px"><canvas id="chart-zone"></canvas></div>
        </div>
        <div class="content-card" style="animation-delay:0.15s;margin-bottom:0">
          <div class="content-card-header"><span class="content-card-title"><i data-lucide="brain"></i> IA — V4 Progressivo</span></div>
          <p style="font-size:11px;color:var(--text-muted);line-height:1.6;margin-bottom:12px">Modelo progressivo com quatro modos (STARTUP, LAG_5, LAG_15, FULL). STARTUP e LAG_5 usam GradientBoosting; LAG_15 e FULL usam ExtraTrees. O modo é escolhido conforme as leituras disponíveis. Os dados reais publicados ficam na tela IA &amp; Previsões.</p>
          <p style="font-size:11px;color:${ai.color};margin-top:12px">${this.esc(ai.text)}</p>
        </div>
      </div>
    `;
    FloodSense.icons();

    const d = this.chartDefaults();

    this.makeChart('chart-week', {
      type: 'line',
      data: {
        labels: ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'],
        datasets: [{
          data: [48,58,52,66,82,90,72],
          borderColor: '#00B8D9', backgroundColor: 'rgba(0,184,217,0.08)',
          tension: 0.4, fill: true, borderWidth: 2,
          pointRadius: 4, pointBackgroundColor: '#00B8D9'
        }]
      },
      options: { ...d, scales: { ...d.scales, y: { ...d.scales.y, ticks: { ...d.scales.y.ticks, callback: v => v+'cm' }, suggestedMin: 0 } } }
    });

    this.makeChart('chart-rain', {
      type: 'bar',
      data: {
        labels: ['00h','03h','06h','09h','12h','15h','18h','21h'],
        datasets: [
          { label: 'Chuva (mm)', data: [5,12,25,18,8,15,30,22], backgroundColor: 'rgba(0,184,217,0.5)', borderRadius: 3, yAxisID: 'y' },
          { label: 'Nível (cm)', data: [45,52,65,72,68,74,88,82], borderColor: '#ef4444', type: 'line', tension: 0.4, borderWidth: 2, pointRadius: 0, yAxisID: 'y1' }
        ]
      },
      options: {
        ...d,
        scales: {
          y:  { ...d.scales.y, position: 'left',  ticks: { ...d.scales.y.ticks, callback: v => v+'mm' } },
          y1: { ...d.scales.y, position: 'right', ticks: { ...d.scales.y.ticks, callback: v => v+'cm' }, grid: { display: false } },
          x:  { ...d.scales.x, grid: { display: false } }
        }
      }
    });

    this.makeChart('chart-zone', {
      type: 'bar',
      data: {
        labels: ['Centro','Z.Norte','Z.Sul','Z.Leste','Z.Oeste','Marginal'],
        datasets: [
          { label: 'Críticos', data: [8,5,4,3,1,4], backgroundColor: 'rgba(239,68,68,0.8)', borderRadius: 3, stack: 's' },
          { label: 'Atenção',  data: [4,4,3,3,2,3], backgroundColor: 'rgba(242,140,0,0.7)', borderRadius: 0, stack: 's' },
          { label: 'Normal',   data: [3,5,7,7,10,5], backgroundColor: 'rgba(22,163,106,0.6)', borderRadius: 0, stack: 's' }
        ]
      },
      options: {
        ...d,
        scales: {
          x: { ...d.scales.x, grid: { display: false } },
          y: { ...d.scales.y, stacked: true }
        }
      }
    });

  },

  /* ═════════════════════════════════════════════
     12. TELA: ALERTAS
  ═════════════════════════════════════════════ */
  renderAlerts() {
    const root = document.getElementById('app-root');
    const crits = this.state.alerts.filter(a => a.type === 'critical');
    const warns = this.state.alerts.filter(a => a.type === 'warning');
    const others = this.state.alerts.filter(a => a.type !== 'critical' && a.type !== 'warning');

    root.innerHTML = `
      <div class="grid-3" style="margin-bottom:12px">
        ${[
          { label:'Alertas Críticos', val:crits.length, color:'var(--red)', icon:'🚨' },
          { label:'Atenção',          val:warns.length, color:'var(--yellow)', icon:'⚠️' },
          { label:'Normalizados (lista)', val:this.state.alerts.filter(a => a.type === 'info').length, color:'var(--green)', icon:'✅' }
        ].map((k,i) => `
          <div class="content-card" style="text-align:center;margin-bottom:0;animation-delay:${i*0.06}s;padding:14px">
            <div style="font-size:24px;margin-bottom:6px">${k.icon}</div>
            <div style="font-size:28px;font-weight:700;color:${k.color};font-family:var(--text-mono)">${k.val}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:3px">${k.label}</div>
          </div>
        `).join('')}
      </div>

      <div class="content-card mb" style="animation-delay:0.12s">
        <div class="content-card-header">
          <span class="content-card-title"><i data-lucide="siren"></i> Alertas Críticos — Ação Imediata</span>
          <button class="btn btn-sm btn-danger" disabled title="Integração com a Defesa Civil ainda não implementada" style="opacity:.55;cursor:not-allowed">
            <i data-lucide="phone"></i> Acionar Defesa Civil
          </button>
        </div>
        ${crits.map(a => `
          <div class="alert-item alert-critical">
            <div class="alert-icon-wrap ic-red"><span style="font-size:16px">${a.icon}</span></div>
            <div class="alert-content">
              <div class="alert-title">${a.zone} <span class="badge badge-red" style="margin-left:6px">${a.badge}</span></div>
              <div class="alert-description">${a.msg}</div>
              <div style="font-size:10px;color:var(--text-muted);margin-top:4px;font-family:var(--text-mono)">Sensor: ${a.sensor}</div>
            </div>
            <div class="alert-time">${a.time}</div>
          </div>
        `).join('')}
      </div>

      <div class="content-card mb" style="animation-delay:0.18s">
        <div class="content-card-header">
          <span class="content-card-title"><i data-lucide="alert-triangle"></i> Atenção</span>
        </div>
        ${warns.map(a => `
          <div class="alert-item alert-warning">
            <div class="alert-icon-wrap ic-yellow"><span style="font-size:16px">${a.icon}</span></div>
            <div class="alert-content">
              <div class="alert-title">${a.zone} <span class="badge badge-yellow" style="margin-left:6px">${a.badge}</span></div>
              <div class="alert-description">${a.msg}</div>
            </div>
            <div class="alert-time">${a.time}</div>
          </div>
        `).join('')}
      </div>

      <div class="content-card" style="animation-delay:0.24s">
        <div class="content-card-header">
          <span class="content-card-title"><i data-lucide="clock"></i> Timeline de Eventos</span>
        </div>
        <div class="timeline">
          ${this.state.alerts.map(a => {
            const dotCls = a.type==='critical'?'dot-red':a.type==='warning'?'dot-yellow':a.type==='info'?'dot-green':'dot-blue';
            return `<div class="timeline-item">
              <div class="timeline-dot ${dotCls}"></div>
              <div class="timeline-time">${a.time} — ${a.sensor}</div>
              <div class="timeline-text"><strong style="color:var(--text-primary)">${a.zone}</strong> — ${a.msg.substring(0,80)}${a.msg.length>80?'...':''}</div>
            </div>`;
          }).join('')}
        </div>
      </div>
    `;
    FloodSense.icons();
  },

  /* ═════════════════════════════════════════════
     12b. RELATÓRIOS EM PDF (abre a janela de impressão: escolha "Salvar como PDF")
  ═════════════════════════════════════════════ */
  async gerarRelatorio(tipo) {
    const esc = s => String(s ?? '—').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
    const numOk = v => typeof v === 'number' && Number.isFinite(v);
    const toMs = v => {
      const n = this.parseNum(v);
      if (n !== null) return n > 1e12 ? n : (n > 1e9 ? n * 1000 : null);
      const t = Date.parse(String(v));
      return Number.isFinite(t) ? t : null;
    };
    const STATUS = { normal: 'Normal', warning: 'Atenção', critical: 'Crítico', offline: 'Offline' };

    // Abrir a janela já no clique evita o bloqueio de pop-up depois do await.
    const janela = window.open('', '_blank');
    if (!janela) {
      this.showToast('warning', 'Pop-up bloqueado', 'Permita pop-ups deste site para gerar o PDF.');
      return;
    }
    janela.document.write('<p style="font-family:Arial,sans-serif;padding:24px">Gerando relatório…</p>');

    const titulos = {
      diario: 'Relatório Diário Completo',
      semanal: 'Histórico Semanal — Nível Hídrico',
      ia: 'Desempenho do Modelo IA'
    };
    const titulo = titulos[tipo] || 'Relatório FloodSense AI';
    const agora = new Date().toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' });
    const linhas = pares => pares.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('');

    let corpo = '';
    try {
      if (tipo === 'diario') {
        const leitura = await this.fetchCurrentRealSensor();
        const pred = this.state.aiPrediction || this.emptyPrediction('loading');
        const ms = leitura ? toMs(leitura.timestamp) : null;
        corpo = `<table>${linhas([
          ['Nível da água (FS-001)', leitura ? leitura.level.toFixed(1) + ' cm' : 'Sem leitura no momento'],
          ['Status do sensor', leitura ? (STATUS[leitura.status] || leitura.status) : '—'],
          ['Última leitura do sensor', ms ? this.fmtSaoPaulo(ms) : '—'],
          ['Previsão da IA (+60 min)', numOk(pred.predicted) ? pred.predicted.toFixed(1) + ' cm' : 'Indisponível'],
          ['Status da IA', this.aiStatusText(pred)]
        ])}</table>`;
      }

      if (tipo === 'semanal') {
        const url = `https://${FIREBASE_HOST}/sensor_history_treinamento/${FIREBASE_SENSOR_ID}.json`;
        const resp = await fetch(url, { cache: 'no-store' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const dados = (await resp.json()) || {};
        const limite = Date.now() - 7 * 24 * 60 * 60 * 1000;
        const niveis = [];
        Object.entries(dados).forEach(([chave, valor]) => {
          const nivel = this.parseNum(valor && typeof valor === 'object' ? valor.level : valor);
          const ms = toMs(valor && typeof valor === 'object' && valor.timestamp !== undefined ? valor.timestamp : chave);
          if (nivel !== null && ms !== null && ms >= limite) niveis.push(nivel);
        });
        if (niveis.length === 0) {
          corpo = '<p>Ainda não há leituras suficientes nos últimos 7 dias para gerar as estatísticas.</p>';
        } else {
          const media = niveis.reduce((a, b) => a + b, 0) / niveis.length;
          corpo = `<table>${linhas([
            ['Leituras nos últimos 7 dias', niveis.length],
            ['Nível mínimo', Math.min(...niveis).toFixed(1) + ' cm'],
            ['Nível máximo', Math.max(...niveis).toFixed(1) + ' cm'],
            ['Nível médio', media.toFixed(1) + ' cm']
          ])}</table>`;
        }
      }

      if (tipo === 'ia') {
        const pred = this.state.aiPrediction || this.emptyPrediction('loading');
        corpo = `<table>${linhas([
          ['Modelo', pred.model || '—'],
          ['Algoritmo', pred.algorithm || '—'],
          ['Versão', pred.version || '—'],
          ['Conjunto de atributos', pred.mode || '—'],
          ['Defasagens usadas (lags)', (pred.lags && pred.lags.length) ? pred.lags.join(', ') : '—'],
          ['Erro médio absoluto no teste', numOk(pred.mae) ? pred.mae.toFixed(2) + ' cm' : '—'],
          ['Previsão atual (+60 min)', numOk(pred.predicted) ? pred.predicted.toFixed(1) + ' cm' : 'Indisponível'],
          ['Status da IA', this.aiStatusText(pred)]
        ])}</table>`;
      }
    } catch (erro) {
      console.error('[FloodSense] Falha ao gerar relatório:', erro);
      corpo = '<p>Não foi possível buscar os dados agora. Verifique a conexão e tente de novo.</p>';
    }

    const html = `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>${esc(titulo)} — FloodSense AI</title>
<style>
  body { font-family: Arial, Helvetica, sans-serif; color: #263238; margin: 32px; }
  h1 { color: #0B1F3A; font-size: 22px; margin: 0 0 4px; }
  .sub { color: #62747E; font-size: 12px; margin-bottom: 22px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { border-bottom: 1px solid #E1EAEE; padding: 9px 8px; text-align: left; }
  th { width: 55%; color: #62747E; font-weight: 600; }
  .nota { font-size: 11px; color: #62747E; border-top: 1px solid #E1EAEE; padding-top: 10px; margin-top: 24px; }
  @media print { body { margin: 14mm; } }
</style></head>
<body>
  <h1>${esc(titulo)}</h1>
  <div class="sub">FloodSense AI · Sensor ${esc(FIREBASE_SENSOR_ID)} (Sensor Centro) · Gerado em ${esc(agora)} (horário de Brasília)</div>
  ${corpo}
  <div class="nota">Dados obtidos do Firebase no momento da geração. Sensor FS-001: dado real (ESP32 + AJ-SR04M). Demais sensores do painel são simulados.</div>
</body></html>`;

    janela.document.open();
    janela.document.write(html);
    janela.document.close();
    setTimeout(() => { try { janela.focus(); janela.print(); } catch (_) {} }, 400);
  },

  /* ═════════════════════════════════════════════
     12c. EXPORTAÇÃO CSV (download direto; separador ';' para abrir no Excel em pt-BR)
  ═════════════════════════════════════════════ */
  async exportarCSV(tipo) {
    const celula = v => {
      const txt = (v === null || v === undefined) ? '' : String(v);
      return /[;"\r\n]/.test(txt) ? '"' + txt.replace(/"/g, '""') + '"' : txt;
    };
    const baixar = (nome, cabecalho, linhas) => {
      const conteudo = [cabecalho, ...linhas].map(l => l.map(celula).join(';')).join('\r\n');
      const blob = new Blob(['\uFEFF' + conteudo], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = nome;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    // Data de hoje no fuso de São Paulo, no formato AAAA-MM-DD
    const hoje = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Sao_Paulo' });

    if (tipo === 'dados') {
      try {
        const url = `https://${FIREBASE_HOST}/sensor_history_treinamento/${FIREBASE_SENSOR_ID}.json`;
        const resp = await fetch(url, { cache: 'no-store' });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const dados = (await resp.json()) || {};
        const toMs = v => {
          const n = this.parseNum(v);
          if (n !== null) return n > 1e12 ? n : (n > 1e9 ? n * 1000 : null);
          const t = Date.parse(String(v));
          return Number.isFinite(t) ? t : null;
        };
        const registros = [];
        Object.entries(dados).forEach(([chave, valor]) => {
          const nivel = this.parseNum(valor && typeof valor === 'object' ? valor.level : valor);
          const ms = toMs(valor && typeof valor === 'object' && valor.timestamp !== undefined ? valor.timestamp : chave);
          if (nivel !== null && ms !== null) registros.push({ ms, nivel });
        });
        if (registros.length === 0) {
          this.showToast('warning', 'Sem dados', 'Não há leituras do FS-001 para exportar.');
          return;
        }
        registros.sort((a, b) => a.ms - b.ms);
        const linhas = registros.map(r => [
          new Date(r.ms).toISOString(),
          this.fmtSaoPaulo(r.ms),
          r.ms,
          r.nivel.toFixed(2).replace('.', ','),
          'REAL (ESP32 · FS-001)'
        ]);
        baixar(`floodsense_dados_FS-001_${hoje}.csv`,
          ['data_hora_utc', 'data_hora_sao_paulo', 'timestamp_ms', 'nivel_agua_cm', 'origem'], linhas);
        this.showToast('success', 'CSV gerado', `${linhas.length} leituras do FS-001 exportadas.`);
      } catch (erro) {
        console.error('[FloodSense] Falha ao exportar dados:', erro);
        this.showToast('critical', 'Falha na exportação', 'Não foi possível buscar os dados. Verifique a conexão.');
      }
      return;
    }

    if (tipo === 'alertas') {
      const alertas = this.state.alerts || [];
      if (alertas.length === 0) {
        this.showToast('warning', 'Sem alertas', 'Não há alertas para exportar.');
        return;
      }
      const linhas = alertas.map(a => [a.id, a.time, a.type, a.badge, a.sensor, a.zone, a.msg, 'SIMULADO']);
      baixar(`floodsense_log_alertas_${hoje}.csv`,
        ['id', 'hora', 'tipo', 'classificacao', 'sensor', 'zona', 'mensagem', 'origem'], linhas);
      this.showToast('success', 'CSV gerado', `${linhas.length} alertas exportados (dados simulados).`);
    }
  },

  /* ═════════════════════════════════════════════
     13. TELA: RELATÓRIOS
  ═════════════════════════════════════════════ */
  renderReports() {
    const root = document.getElementById('app-root');
    const ai = this.aiSummary();
    const aiPred = this.state.aiPrediction || this.emptyPrediction('loading');
    root.innerHTML = `
      <div class="grid-2" style="margin-bottom:12px">
        <div class="content-card" style="margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="file-text"></i> Relatórios Disponíveis</span>
          </div>
          ${[
            { icon:'📊', key:'diario', name:'Relatório Diário Completo', meta:'PDF · Sensor FS-001 e previsão da IA · Agora', color:'var(--blue-dim)', btn:'pdf' },
            { icon:'📈', key:'semanal', name:'Histórico Semanal — Nível Hídrico', meta:'PDF · Estatísticas do FS-001 · Últimos 7 dias', color:'var(--blue-dim)', btn:'pdf' },
            { icon:'🤖', key:'ia', name:'Desempenho do Modelo IA', meta:'PDF · Modelo, erro e previsão atual', color:'var(--purple-dim)', btn:'pdf' },
            { icon:'📋', csv:'dados', name:'Dados Brutos — Sensores', meta:'CSV · Leituras do FS-001 (REAL) · Exportação raw', color:'var(--green-dim)', btn:'csv' },
            { icon:'🚨', csv:'alertas', name:'Log de Alertas', meta:'CSV · Alertas do painel (SIMULADOS)', color:'var(--red-dim)', btn:'csv' },
          ].map((r,i) => `
            <div class="report-card" style="animation-delay:${i*0.06}s;background:${r.color}">
              <div class="report-icon" style="background:rgba(11,31,58,0.05);border-radius:var(--radius-sm)">
                <span style="font-size:20px">${r.icon}</span>
              </div>
              <div class="report-info">
                <div class="report-name">${r.name}</div>
                <div class="report-meta">${r.meta}</div>
              </div>
              <button class="btn btn-sm btn-outline report-btn"
                onclick="${r.key ? `FloodSense.gerarRelatorio('${r.key}')` : `FloodSense.exportarCSV('${r.csv}')`}">
                <i data-lucide="download"></i>
                ${r.btn.toUpperCase()}
              </button>
            </div>
          `).join('')}
        </div>
        <div class="content-card" style="margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="bar-chart-2"></i> Estatísticas do Período · SIMULADO</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:10px">
            ${[
              ['Total de Leituras (hoje) · simulado', '86.400', 'var(--blue)'],
              ['Alertas Emitidos (mês) · simulado', '142', 'var(--red)'],
              ['Tempo Médio de Resposta',      '3.2 min','var(--yellow)'],
              ['Sensores Ativos',              this.state.sensors.filter(x => x.status !== 'offline').length + '/' + this.state.sensors.length, 'var(--green)'],
              ['Status da IA',                 this.aiStatusText(aiPred), this.aiStatusColor(aiPred)],
              ['Previsão IA +60 min (FS-001)', ai.short, ai.color],
              ['Disponibilidade do Sistema · simulado', '99.7%', 'var(--blue)'],
            ].map(([label, val, color]) => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border-3)">
                <span style="font-size:12px;color:var(--text-secondary)">${label}</span>
                <span style="font-family:var(--text-mono);font-weight:700;color:${color};font-size:13px">${val}</span>
              </div>
            `).join('')}
          </div>
          <div style="margin-top:14px;padding:12px;background:rgba(0,184,217,0.05);border:1px solid rgba(0,184,217,0.18);border-radius:var(--radius-sm);font-size:11px;color:var(--text-secondary)">
            📌 <strong style="color:var(--text-primary)">Nota acadêmica:</strong> Os PDFs abrem a janela de impressão do navegador
            (escolha "Salvar como PDF"). Os CSV de leituras usam dados reais do FS-001; o log de alertas e as estatísticas
            marcadas como simuladas não são dados medidos.
          </div>
        </div>
      </div>
    `;
    FloodSense.icons();
  },

  /* ═════════════════════════════════════════════
     14. TELA: CONFIGURAÇÕES
  ═════════════════════════════════════════════ */
  renderConfig() {
    const root = document.getElementById('app-root');
    const fbOk = this.state.realSensor?.ok === true;
    const aiOk = (this.state.aiPrediction || {}).available === true;
    root.innerHTML = `
      <div class="grid-2" style="margin-bottom:12px">
        <!-- Alertas -->
        <div class="content-card" style="margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="bell"></i> Configurações de Alerta</span>
          </div>
          ${[
            ['Alertas em Tempo Real', 'Notificações instantâneas via sistema', true],
            ['Alerta Sonoro', 'Áudio para eventos críticos', false],
            ['Notificação por E-mail', 'Envio automático para gestores', true],
            ['Alerta WhatsApp (via API)', 'Mensagem para Defesa Civil', false],
            ['Relatório Diário Automático', 'Gerado às 07h00 todo dia', true],
          ].map(([label, desc, checked]) => `
            <div class="config-row">
              <div class="config-label-wrap">
                <div class="config-label">${label}</div>
                <div class="config-desc">${desc}</div>
              </div>
              <label class="toggle">
                <input type="checkbox" ${checked ? 'checked' : ''}>
                <span class="toggle-track"></span>
              </label>
            </div>
          `).join('')}
        </div>

        <!-- Limites de nível -->
        <div class="content-card" style="margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="sliders"></i> Limites de Nível Hídrico</span>
          </div>
          ${[
            ['Nível de Atenção (Laranja)', '60', 'cm — Monitoramento intensificado'],
            ['Nível Crítico (Vermelho)', '90', 'cm — Alerta e acionamento'],
            ['Nível de Emergência', '110', 'cm — Evacuação imediata'],
          ].map(([label, val, desc]) => `
            <div class="config-row" style="flex-direction:column;align-items:flex-start;gap:8px">
              <div>
                <div class="config-label">${label}</div>
                <div class="config-desc">${desc}</div>
              </div>
              <div style="display:flex;align-items:center;gap:8px">
                <input type="number" value="${val}" min="0" max="200"
                  style="background:var(--bg-input);border:1px solid var(--border);border-radius:var(--radius-sm);padding:6px 10px;color:var(--text-primary);font-family:var(--text-mono);width:80px;outline:none;font-size:13px">
                <span style="font-size:12px;color:var(--text-muted)">cm</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>

      <div class="grid-2">
        <!-- Sistema -->
        <div class="content-card" style="margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="settings"></i> Sistema</span>
          </div>
          ${[
            ['Intervalo de Leitura', '3 segundos (demo) / 5 min (produção)', true],
            ['Backup Automático', 'Sincronização com Firebase a cada hora', true],
            ['Modo Debug', 'Logs detalhados no console', false],
            ['Cache de Dados', 'Armazena últimas 24h localmente', true],
          ].map(([label, desc, checked]) => `
            <div class="config-row">
              <div class="config-label-wrap">
                <div class="config-label">${label}</div>
                <div class="config-desc">${desc}</div>
              </div>
              <label class="toggle">
                <input type="checkbox" ${checked ? 'checked' : ''}>
                <span class="toggle-track"></span>
              </label>
            </div>
          `).join('')}
          <div style="margin-top:14px">
            <button class="btn btn-primary" onclick="FloodSense.showToast('success','Configurações Salvas','Alterações aplicadas com sucesso.')">
              <i data-lucide="save"></i> Salvar Configurações
            </button>
          </div>
        </div>

        <!-- Status da infraestrutura -->
        <div class="content-card" style="margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="server"></i> Status da Infraestrutura</span>
          </div>
          ${[
            ['Firebase Realtime Database', fbOk ? 'online' : 'warning', fbOk ? '● Conectado' : '◑ Sem resposta'],
            ['Sensor FS-001 (ESP32 + AJ-SR04M)', fbOk ? 'online' : 'warning', fbOk ? '● Dado real' : '◑ Sem leitura'],
            [`Modelo IA (Python · ${this.esc(this.getAIModelName() || 'modelo de IA')})`, aiOk ? 'online' : 'warning', aiOk ? '● Previsão publicada' : '◑ Aguardando previsão'],
            ['Sensores FS-002 a FS-012', 'warning', '◑ Simulados (demo)'],
            ['API INMET (Clima)', 'warning', '◑ Não integrada'],
            ['Defesa Civil API', 'warning', '◑ Não integrada'],
          ].map(([name, status, label]) => {
            const color = status === 'online' ? 'var(--green)' : status === 'warning' ? 'var(--yellow)' : 'var(--red)';
            const bg    = status === 'online' ? 'rgba(22,163,106,0.08)' : status === 'warning' ? 'rgba(242,140,0,0.08)' : 'rgba(220,69,69,0.08)';
            const border= status === 'online' ? 'rgba(22,163,106,0.18)' : status === 'warning' ? 'rgba(242,140,0,0.18)' : 'rgba(220,69,69,0.18)';
            return `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:${bg};border:1px solid ${border};border-radius:var(--radius-sm);margin-bottom:6px">
              <span style="font-size:12px;color:var(--text-secondary)">${name}</span>
              <span style="font-size:11px;font-family:var(--text-mono);color:${color};font-weight:600">${label}</span>
            </div>`;
          }).join('')}
        </div>
      </div>
    `;
    FloodSense.icons();
  },

  /* ═════════════════════════════════════════════
     15. TOAST NOTIFICATIONS
  ═════════════════════════════════════════════ */

  /**
   * Exibe uma notificação toast.
   * @param {string} type — 'critical' | 'warning' | 'success' | 'info'
   * @param {string} title
   * @param {string} desc
   * @param {number} duration — ms (padrão: 5000)
   */
  showToast(type, title, desc, duration = 5000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = { critical: '🚨', warning: '⚠️', success: '✅', info: 'ℹ️' };
    const id = `toast-${Date.now()}-${Math.floor(Math.random() * 1e4)}`;

    const el = document.createElement('div');
    el.className = `toast toast-${type === 'critical' ? 'critical' : type === 'warning' ? 'warning' : type === 'success' ? 'success' : 'info'}`;
    el.id = id;
    el.innerHTML = `
      <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
      <div class="toast-body">
        <div class="toast-title">${title}</div>
        <div class="toast-desc">${desc}</div>
      </div>
      <button class="toast-close" onclick="FloodSense.dismissToast('${id}')">✕</button>
    `;

    container.appendChild(el);

    setTimeout(() => this.dismissToast(id), duration);
  },

  dismissToast(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('toast-exit');
    setTimeout(() => el.remove(), 300);
  },

  /* ═════════════════════════════════════════════
     16. UTILITÁRIOS DE UI
  ═════════════════════════════════════════════ */

  /** Inicia o relógio */
  startClock() {
    const tick = () => {
      const now = new Date();
      const hh = String(now.getHours()).padStart(2, '0');
      const mm = String(now.getMinutes()).padStart(2, '0');
      const ss = String(now.getSeconds()).padStart(2, '0');
      const el = document.getElementById('live-clock');
      if (el) el.textContent = `${hh}:${mm}:${ss}`;
    };
    tick();
    this.state.clockInterval = setInterval(tick, 1000);
  },

  /** Abre/fecha a sidebar (mobile) */
  toggleSidebar() {
    this.state.sidebarOpen = !this.state.sidebarOpen;
    document.getElementById('sidebar').classList.toggle('open', this.state.sidebarOpen);
    document.getElementById('sidebar-overlay').classList.toggle('visible', this.state.sidebarOpen);
  },
  closeSidebar() {
    this.state.sidebarOpen = false;
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('visible');
  }
};

/* Estado inicial da previsão da IA (precisa dos métodos do objeto, por isso fica aqui) */
FloodSense.state.aiPrediction = FloodSense.emptyPrediction('loading');

/* ═══════════════════════════════════════════════════════════════════
   17. INICIALIZAÇÃO
═══════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  FloodSense.icons();

  // Configurações globais padrão do Chart.js
  if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = "'Space Grotesk', system-ui, sans-serif";
    Chart.defaults.color = '#64748b';
    Chart.defaults.borderColor = 'rgba(11,31,58,0.08)';
  }

  console.log(
    '%c FloodSense AI ',
    'background:#0066FF;color:#fff;font-weight:bold;padding:4px 8px;border-radius:4px',
    '\nTCC — Sistemas de Informação'
  );
});