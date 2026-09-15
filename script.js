/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║         FloodSense AI — script.js                               ║
 * ║         Versão: 3.0  |  TCC — Sistemas de Informação           ║
 * ╠══════════════════════════════════════════════════════════════════╣
 * ║  ÍNDICE DO ARQUIVO:                                              ║
 * ║  01. Dados simulados (sensores IoT)                              ║
 * ║  02. Estado global da aplicação                                  ║
 * ║  03. Funções utilitárias                                         ║
 * ║  04. Autenticação (login/logout)                                 ║
 * ║  05. Simulação de dados IoT (fetchIoTData)                       ║
 * ║  06. Sistema de navegação (navigate / renderScreen)              ║
 * ║  07. Tela: Dashboard                                             ║
 * ║  08. Tela: Sensores                                              ║
 * ║  09. Tela: Mapa Interativo (Leaflet)                             ║
 * ║  10. Tela: IA & Previsões                                        ║
 * ║  11. Tela: Análise Gráfica                                       ║
 * ║  12. Tela: Alertas                                               ║
 * ║  13. Tela: Relatórios                                            ║
 * ║  14. Tela: Configurações                                         ║
 * ║  15. Sistema de Toast Notifications                              ║
 * ║  16. Utilitários de UI (clock, sidebar, badges)                  ║
 * ║  17. Inicialização da aplicação                                  ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

/* ═══════════════════════════════════════════════════════════════════
   01. DADOS SIMULADOS — BASE DE SENSORES IoT
   Em produção, esses dados viriam da API do backend.
   Cada objeto representa um sensor ESP32 instalado em campo.
═══════════════════════════════════════════════════════════════════ */

/**
 * DATASET: 12 sensores IoT simulados
 * Coordenadas reais de São Paulo para exibição no Leaflet.
 *
 * ─── GUIA DE INTEGRAÇÃO COM ESP32/ARDUINO ───────────────────────
 * Quando o hardware estiver instalado, substitua este array por
 * uma chamada à sua API:
 *
 *   const SENSORS = await FloodSense.fetchIoTData();
 *
 * Seu endpoint deve retornar JSON com a mesma estrutura abaixo.
 * Veja a função fetchIoTData() mais adiante (seção 05).
 * ─────────────────────────────────────────────────────────────────
 */
/**
 * ─── PROTÓTIPO — SENSOR REAL (FS-001) ───────────────────────────
 * Cole aqui a URL do seu Realtime Database (sem "https://" e sem
 * barra final), a mesma que você configurou em floodsense_sensor.ino.
 * Ex: "floodsense-ai-tcc-default-rtdb.firebaseio.com"
 *
 * Deixe como '' pra rodar 100% simulado (sem hardware conectado).
 * ──────────────────────────────────────────────────────────────── */
const FIREBASE_HOST = 'floodsense-ai-7a6b9-default-rtdb.firebaseio.com';
const FIREBASE_SENSOR_ID = 'FS-001';

const SENSORS_BASE = [
  {
    id: 'FS-001',
    name: 'Sensor Centro',
    location: 'Praça da Sé, Centro',
    bairro: 'Centro',
    lat: -23.5505,
    lng: -46.6333,
    level: 115,    // cm — nível da água
    temp: 23.4,    // °C
    humidity: 88,  // %
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
  { id: 1, type: 'critical', icon: '🚨', zone: 'Centro — Praça da Sé', sensor: 'FS-001',
    msg: 'Nível atingiu 115cm. Risco iminente de inundação. Defesa Civil acionada.', time: '09:14', badge: 'CRÍTICO' },
  { id: 2, type: 'critical', icon: '🚨', zone: 'Zona Norte — Santana', sensor: 'FS-002',
    msg: 'Nível em 92cm, ultrapassando limite crítico (90cm). Evacuação preventiva recomendada.', time: '09:12', badge: 'CRÍTICO' },
  { id: 3, type: 'warning', icon: '⚠️', zone: 'Zona Sul — Santo Amaro', sensor: 'FS-003',
    msg: 'Nível em 85cm. Tendência crescente. Monitoramento intensificado.', time: '09:10', badge: 'ATENÇÃO' },
  { id: 4, type: 'warning', icon: '⚠️', zone: 'Marginal Tietê — KM12', sensor: 'FS-006',
    msg: 'Umidade do solo em 93%. Alta probabilidade de saturação hídrica nas próximas 2h.', time: '09:05', badge: 'ATENÇÃO' },
  { id: 5, type: 'warning', icon: '⚠️', zone: 'Mandaqui', sensor: 'FS-010',
    msg: 'Nível em 61cm com previsão de chuvas fortes. Equipes em standby.', time: '08:55', badge: 'ATENÇÃO' },
  { id: 6, type: 'info', icon: '✅', zone: 'Jabaquara', sensor: 'FS-008',
    msg: 'Situação normalizada. Nível caiu para 33cm após recuo das chuvas.', time: '08:30', badge: 'NORMAL' },
  { id: 7, type: 'info', icon: '✅', zone: 'Pinheiros', sensor: 'FS-007',
    msg: 'Leitura estável. Nível dentro dos parâmetros normais (55cm).', time: '08:00', badge: 'NORMAL' },
  { id: 8, type: 'system', icon: '⚫', zone: 'Sistema — Campo Limpo', sensor: 'FS-012',
    msg: 'Sensor FS-012 sem comunicação há 52 minutos. Equipe de manutenção acionada via sistema.', time: '07:22', badge: 'OFFLINE' }
];

/* ═══════════════════════════════════════════════════════════════════
   02. ESTADO GLOBAL DA APLICAÇÃO
   Objeto central que controla toda a lógica do sistema.
═══════════════════════════════════════════════════════════════════ */
const FloodSense = {

  /** Estado reativo da aplicação */
  state: {
    loggedIn:    false,
    currentScreen: 'dashboard',
    sensors:     JSON.parse(JSON.stringify(SENSORS_BASE)), // cópia profunda
    alerts:      ALERTS_DATA,
    sidebarOpen: false,
    iotInterval: null,    // referência do setInterval do IoT
    clockInterval: null,  // referência do relógio
    chartInstances: {},   // Chart.js — manter refs para destruição correta
    leafletMap: null,     // instância do mapa Leaflet
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
    if (!ctx) return null;
    const chart = new Chart(ctx, config);
    this.state.chartInstances[canvasId] = chart;
    return chart;
  },

  /** Configuração global padrão do Chart.js — tema dark */
  chartDefaults() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0f0f0f',
          borderColor: '#1e293b',
          borderWidth: 1,
          titleColor: '#ffffff',
          bodyColor: '#94a3b8',
          padding: 10,
          cornerRadius: 8,
        }
      },
      scales: {
        x: {
          ticks: { color: '#475569', font: { size: 10, family: 'JetBrains Mono' } },
          grid:  { color: 'rgba(30,41,59,0.5)' }
        },
        y: {
          ticks: { color: '#475569', font: { size: 10, family: 'JetBrains Mono' } },
          grid:  { color: 'rgba(30,41,59,0.5)' }
        }
      }
    };
  },

  /* ═════════════════════════════════════════════
     04. AUTENTICAÇÃO
  ═════════════════════════════════════════════ */

  /** Manipula submit do formulário de login */
  handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('input-email').value.trim();
    const pass  = document.getElementById('input-password').value;
    const err   = document.getElementById('login-error');
    const btn   = document.getElementById('btn-login');

    // Credenciais válidas para demonstração
    const VALID_EMAIL = 'admin@floodsense.ai';
    const VALID_PASS  = 'floodsense2025';

    // Loading state
    btn.classList.add('loading');
    btn.innerHTML = '<span>Verificando...</span>';

    // Simula latência de rede (300ms)
    setTimeout(() => {
      if (email === VALID_EMAIL && pass === VALID_PASS) {
        err.textContent = '';
        this.state.loggedIn = true;
        this.bootApp();
      } else {
        err.textContent = '⚠️ E-mail ou senha incorretos. Tente novamente.';
        btn.classList.remove('loading');
        btn.innerHTML = '<i data-lucide="log-in"></i><span>Entrar no Sistema</span>';
        lucide.createIcons();
      }
    }, 300);
  },

  /** Mostra/oculta campo de senha */
  togglePassword() {
    const input = document.getElementById('input-password');
    input.type = input.type === 'password' ? 'text' : 'password';
  },

  /** Encerra sessão e volta ao login */
  logout() {
    this.state.loggedIn = false;
    clearInterval(this.state.iotInterval);
    clearInterval(this.state.clockInterval);
    // Destrói mapa Leaflet se existir
    if (this.state.leafletMap) {
      this.state.leafletMap.remove();
      this.state.leafletMap = null;
    }
    document.getElementById('app-shell').hidden = true;
    document.getElementById('login-screen').style.display = 'flex';
    this.showToast('info', 'Sessão encerrada', 'Você saiu do sistema com segurança.');
  },

  /** Inicia o aplicativo após login bem-sucedido */
  bootApp() {
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app-shell').hidden = false;
    lucide.createIcons();

    // Inicia relógio
    this.startClock();

    // Inicia simulação IoT
    this.startIoTSimulation();

    // Renderiza tela inicial
    this.navigate('dashboard');

    // Notificação de boas-vindas
    setTimeout(() => {
      this.showToast('critical', '🚨 Alerta Crítico', 'Sensor FS-001 (Centro): nível em 115cm!');
    }, 1500);
    setTimeout(() => {
      this.showToast('warning', '⚠️ IA detectou risco', 'Prob. de enchente: 92% nas próximas 6h.');
    }, 3500);
  },

  /* ═════════════════════════════════════════════
     05. SIMULAÇÃO DE DADOS IoT
     
     ─── INTEGRAÇÃO FUTURA COM ESP32/ARDUINO ────
     Para conectar sensores reais, faça o seguinte:
     
     1. Seu ESP32 deve enviar dados via HTTP POST:
        POST http://seu-servidor.com/api/sensors
        Body: { "sensorId": "FS-001", "level": 112.5,
                "temp": 23.1, "humidity": 87 }
     
     2. backend (Node.js/FastAPI) salva no banco
        (Firebase/MongoDB) e expõe um endpoint GET:
        GET http://seu-servidor.com/api/sensors
        → Retorna array de objetos com a mesma estrutura
          de SENSORS_BASE acima.
     
     3. Descomente o bloco fetchFromAPI() abaixo e
        remova a chamada de simulação local.
     ─────────────────────────────────────────────
  ═════════════════════════════════════════════ */

  /**
   * Busca dados dos sensores.
   * AGORA: simula variações de ±2cm a cada chamada.
   * FUTURO: troca por chamada real à API.
   */
  async fetchIoTData() {
    /* ─────────────────────────────────────────────────────────────
       INTEGRAÇÃO REAL — DESCOMENTAR QUANDO A API ESTIVER PRONTA
       
       ⚠️ ATENÇÃO: Substitua 'http://localhost:3000' pela URL
          real do seu servidor Node.js / FastAPI / Firebase.
    ──────────────────────────────────────────────────────────────

    try {
      const response = await fetch('http://localhost:3000/api/sensors', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          // Adicione seu token de autenticação aqui:
          // 'Authorization': 'Bearer SEU_TOKEN_JWT'
        }
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      // data deve ser um array com a mesma estrutura de SENSORS_BASE
      return data;

    } catch (error) {
      console.error('[FloodSense] Erro ao buscar dados da API:', error);
      // Em caso de falha, mantém os dados locais (fallback)
      return this.state.sensors;
    }

    ─────────────────────────────────────────────────────────────── */

    /* ── MODO SIMULAÇÃO (base para os sensores sem hardware) ─────── */
    const simulados = this.state.sensors.map(s => {
      if (s.status === 'offline') return s;

      // Variação aleatória de ±2 cm (simula flutuação real do sensor)
      const delta = (Math.random() - 0.45) * 4;
      const newLevel = Math.max(5, Math.min(130, parseFloat((s.level + delta).toFixed(1))));

      // Recalcula status com base no nível
      let newStatus = 'normal';
      if (newLevel >= 90) newStatus = 'critical';
      else if (newLevel >= 60) newStatus = 'warning';

      // Temperatura: ±0.3°C
      const newTemp = parseFloat((s.temp + (Math.random() - 0.5) * 0.6).toFixed(1));

      // Horário atual
      const now = new Date();
      const hh  = String(now.getHours()).padStart(2, '0');
      const mm  = String(now.getMinutes()).padStart(2, '0');
      const ss  = String(now.getSeconds()).padStart(2, '0');

      return { ...s, level: newLevel, temp: newTemp, status: newStatus, lastRead: `${hh}:${mm}:${ss}` };
    });

    /* ── PROTÓTIPO — SUBSTITUI O FS-001 PELO DADO REAL DO FIREBASE ──
       Se FIREBASE_HOST estiver vazio, ou a requisição falhar (ESP32
       desligado, sem rede, etc.), mantém o valor simulado do FS-001
       como fallback — o dashboard nunca quebra por causa do hardware. */
    if (!FIREBASE_HOST) return simulados;

    try {
      const url = `https://${FIREBASE_HOST}/sensors/${FIREBASE_SENSOR_ID}.json`;
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const real = await response.json(); // { level, status } vindo do ESP32
      if (!real || typeof real.level !== 'number') return simulados;

      const now = new Date();
      const hh  = String(now.getHours()).padStart(2, '0');
      const mm  = String(now.getMinutes()).padStart(2, '0');
      const ss  = String(now.getSeconds()).padStart(2, '0');

      return simulados.map(s => {
        if (s.id !== FIREBASE_SENSOR_ID) return s;
        return {
          ...s,
          level: real.level,
          status: real.status || s.status,
          lastRead: `${hh}:${mm}:${ss}`
        };
      });
    } catch (error) {
      console.warn('[FloodSense] Sensor real indisponível, usando simulação para', FIREBASE_SENSOR_ID, error);
      return simulados;
    }
  },

  /** Inicia o polling de dados IoT a cada 3 segundos */
  startIoTSimulation() {
    const tick = async () => {
      const updated = await this.fetchIoTData();
      this.state.sensors = updated;
      this.onIoTUpdate();
    };

    // Primeira chamada imediata
    tick();

    // Polling a cada 3 segundos
    // ⚠️ Em produção com API real, use WebSocket ou SSE em vez de polling.
    this.state.iotInterval = setInterval(tick, 3000);
  },

  /**
   * Callback chamado após cada atualização dos dados IoT.
   * Atualiza apenas os elementos da UI que mudaram (evita re-render completo).
   */
  onIoTUpdate() {
    const s = this.state.sensors;

    // Atualiza contadores na navbar
    const online = s.filter(x => x.status !== 'offline').length;
    const elem   = document.getElementById('online-count');
    if (elem) elem.textContent = online;

    // Atualiza contagem no nav
    const navCount = document.getElementById('nav-count-sensors');
    if (navCount) navCount.textContent = s.length;

    // Conta alertas críticos + warnings
    const alertCount = s.filter(x => x.status === 'critical' || x.status === 'warning').length;
    const navAlerts  = document.getElementById('nav-count-alerts');
    if (navAlerts) navAlerts.textContent = alertCount;

    // Atualiza barra de alerta crítico
    const criticals = s.filter(x => x.status === 'critical');
    const critBar   = document.getElementById('critical-bar');
    const critText  = document.getElementById('critical-bar-text');
    if (critBar && critText) {
      if (criticals.length > 0) {
        critBar.classList.remove('hidden');
        critText.textContent = `${criticals[0].name}: CRÍTICO ${criticals[0].level}cm`;
      } else {
        critBar.classList.add('hidden');
      }
    }

    // Se estiver na tela do dashboard, atualiza KPIs e gráfico
    if (this.state.currentScreen === 'dashboard') {
      this.updateDashboardKPIs();
      this.updateDashboardChart();
    }

    // Se estiver na tela de sensores, re-renderiza a tabela
    if (this.state.currentScreen === 'sensors') {
      this.renderSensorTable();
    }

    // Se estiver no mapa, atualiza marcadores
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
    // Encerra instâncias anteriores (mapa, etc.)
    if (this.state.currentScreen === 'map' && screenName !== 'map') {
      if (this.state.leafletMap) {
        this.state.leafletMap.remove();
        this.state.leafletMap = null;
      }
    }

    this.state.currentScreen = screenName;

    // Atualiza botões da sidebar
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.screen === screenName);
    });

    // Atualiza título e subtítulo da navbar
    const titles = {
      dashboard: ['Dashboard Principal', 'São Paulo · SP · Brasil — Monitoramento em Tempo Real'],
      sensors:   ['Sensores IoT', '12 sensores instalados · Leitura automática a cada 3s'],
      map:       ['Mapa Interativo', 'Localização georreferenciada dos sensores — OpenStreetMap'],
      ai:        ['IA & Previsões', 'Modelo LSTM + Random Forest · Acurácia 92%'],
      charts:    ['Análise Gráfica', 'Histórico de 24h · Dados comparativos por região'],
      alerts:    ['Central de Alertas', '3 alertas ativos · 2 críticos · 1 atenção'],
      reports:   ['Relatórios', 'Exportação PDF e CSV · Histórico completo'],
      config:    ['Configurações', 'Parâmetros do sistema, sensores e alertas']
    };

    const [title, sub] = titles[screenName] || ['FloodSense AI', ''];
    const titleEl = document.getElementById('page-title');
    const subEl   = document.getElementById('page-subtitle');
    if (titleEl) titleEl.textContent = title;
    if (subEl)   subEl.textContent   = sub;

    // Renderiza o conteúdo da tela
    this.renderScreen(screenName);

    // Fecha sidebar no mobile após navegação
    this.closeSidebar();
  },

  /**
   * Limpa o #app-root e renderiza a tela correspondente.
   * Este é o "roteador" central do sistema.
   */
  renderScreen(screenName) {
    const root = document.getElementById('app-root');
    if (!root) return;

    // Limpa conteúdo anterior e reinicia animação
    root.innerHTML = '';
    root.style.animation = 'none';
    root.offsetHeight; // reflow
    root.style.animation = '';

    // Destrói charts anteriores
    Object.keys(this.state.chartInstances).forEach(id => this.destroyChart(id));

    // Rota para a tela correspondente
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

    // Re-renderiza ícones Lucide após injetar HTML
    lucide.createIcons();
  },

  /* ═════════════════════════════════════════════
     07. TELA: DASHBOARD
  ═════════════════════════════════════════════ */
  renderDashboard() {
    const root = document.getElementById('app-root');
    root.innerHTML = `
      <!-- KPIs -->
      <div class="kpi-grid" id="kpi-grid"></div>

      <!-- Gráficos principais -->
      <div class="grid-2" style="margin-bottom:12px">
        <div class="chart-card" style="animation-delay:0.1s">
          <div class="chart-header">
            <span class="chart-title">
              <i data-lucide="trending-up"></i> Nível da Água — Últimas 24h
            </span>
            <span class="chart-meta" id="chart-update">ao vivo</span>
          </div>
          <div class="chart-wrap" style="height:190px">
            <canvas id="chart-line"></canvas>
          </div>
          <div class="legend-row">
            <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div>Centro</div>
            <div class="legend-item"><div class="legend-dot" style="background:#facc15"></div>Zona Norte</div>
            <div class="legend-item"><div class="legend-dot" style="background:#38bdf8"></div>Média Geral</div>
          </div>
        </div>
        <div class="chart-card" style="animation-delay:0.15s">
          <div class="chart-header">
            <span class="chart-title">
              <i data-lucide="bar-chart-3"></i> Alertas por Região
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
            <span class="chart-title"><i data-lucide="pie-chart"></i> Distribuição de Risco</span>
          </div>
          <div class="chart-wrap" style="height:160px">
            <canvas id="chart-pie"></canvas>
          </div>
          <div class="legend-row" style="justify-content:center;margin-top:10px">
            <div class="legend-item"><div class="legend-dot" style="background:#22c55e"></div>Normal</div>
            <div class="legend-item"><div class="legend-dot" style="background:#facc15"></div>Atenção</div>
            <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div>Crítico</div>
          </div>
        </div>
        <div class="chart-card" style="animation-delay:0.25s">
          <div class="chart-header">
            <span class="chart-title"><i data-lucide="radio"></i> Sensores Online/Offline</span>
          </div>
          <div class="chart-wrap" style="height:160px">
            <canvas id="chart-online"></canvas>
          </div>
        </div>
        <div class="content-card" style="animation-delay:0.3s;margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="bell"></i> Alertas Recentes</span>
          </div>
          ${this.state.alerts.slice(0,3).map(a => {
            const cls = a.type === 'critical' ? 'alert-critical' : a.type === 'warning' ? 'alert-warning' : 'alert-info';
            return `<div class="alert-item ${cls}" style="padding:10px 12px;margin-bottom:6px">
              <div style="font-size:16px">${a.icon}</div>
              <div class="alert-content">
                <div class="alert-title" style="font-size:12px">${a.zone}</div>
                <div class="alert-description" style="font-size:10px">${a.msg.substring(0,70)}...</div>
              </div>
              <div class="alert-time">${a.time}</div>
            </div>`;
          }).join('')}
        </div>
      </div>
    `;

    this.updateDashboardKPIs();
    lucide.createIcons();
    this.initDashboardCharts();
  },

  /** Calcula e injeta os 6 KPIs */
  updateDashboardKPIs() {
    const s      = this.state.sensors;
    const online  = s.filter(x => x.status !== 'offline');
    const offline = s.filter(x => x.status === 'offline');
    const crits   = s.filter(x => x.status === 'critical');
    const warns   = s.filter(x => x.status === 'warning');
    const avgLvl  = online.length ? (online.reduce((a, x) => a + x.level, 0) / online.length).toFixed(1) : 0;
    const maxLvl  = Math.max(...online.map(x => x.level));
    const floodProb = Math.min(99, Math.round(60 + crits.length * 10 + warns.length * 4));

    const kpis = [
      {
        label: 'Sensores Online', value: online.length, sub: `${offline.length} offline`,
        type: 'blue', icon: 'radio', iconCls: 'ic-blue', valCls: 'col-blue',
        trend: `${Math.round(online.length / s.length * 100)}% uptime`, trendType: 'flat'
      },
      {
        label: 'Nível Médio H₂O', value: avgLvl + 'cm', sub: `Máx: ${maxLvl}cm`,
        type: avgLvl >= 90 ? 'red' : avgLvl >= 60 ? 'yellow' : 'green',
        icon: 'droplets', iconCls: avgLvl >= 90 ? 'ic-red' : avgLvl >= 60 ? 'ic-yellow' : 'ic-green',
        valCls: avgLvl >= 90 ? 'col-red' : avgLvl >= 60 ? 'col-yellow' : 'col-green',
        trend: avgLvl >= 60 ? '▲ Acima do normal' : '▼ Normal', trendType: avgLvl >= 60 ? 'up' : 'down'
      },
      {
        label: 'Prob. Enchente (6h)', value: floodProb + '%', sub: 'Modelo LSTM+RF',
        type: floodProb >= 70 ? 'red' : floodProb >= 50 ? 'yellow' : 'green',
        icon: 'brain', iconCls: 'ic-purple', valCls: floodProb >= 70 ? 'col-red' : 'col-yellow',
        trend: floodProb >= 70 ? '▲ Risco elevado' : '— Estável', trendType: floodProb >= 70 ? 'up' : 'flat'
      },
      {
        label: 'Alertas Ativos', value: crits.length + warns.length, sub: `${crits.length} críticos · ${warns.length} atenção`,
        type: crits.length > 0 ? 'red' : warns.length > 0 ? 'yellow' : 'green',
        icon: 'bell', iconCls: crits.length > 0 ? 'ic-red' : 'ic-yellow', valCls: crits.length > 0 ? 'col-red' : 'col-yellow',
        trend: crits.length > 0 ? '▲ Ação imediata' : 'Monitorando', trendType: crits.length > 0 ? 'up' : 'flat'
      },
      {
        label: 'Áreas Monitoradas', value: '8', sub: 'Zonas cobertas',
        type: 'blue', icon: 'map-pin', iconCls: 'ic-blue', valCls: 'col-blue',
        trend: 'SP · Grande SP', trendType: 'flat'
      },
      {
        label: 'Status da IA', value: '92%', sub: 'Acurácia atual',
        type: 'green', icon: 'cpu', iconCls: 'ic-green', valCls: 'col-green',
        trend: '▲ +14% vs baseline', trendType: 'down'
      }
    ];

    const grid = document.getElementById('kpi-grid');
    if (!grid) return;
    grid.innerHTML = kpis.map((k, i) => `
      <div class="kpi-card kpi-${k.type}" style="animation-delay:${i * 0.05}s">
        <div class="kpi-header">
          <span class="kpi-label">${k.label}</span>
          <div class="kpi-icon ${k.iconCls}"><i data-lucide="${k.icon}"></i></div>
        </div>
        <div class="kpi-value ${k.valCls}">${k.value}</div>
        <div class="kpi-sub">${k.sub}</div>
        <span class="kpi-trend trend-${k.trendType}">${k.trend}</span>
      </div>
    `).join('');
    lucide.createIcons();
  },

  /** Inicializa os 4 gráficos do dashboard */
  initDashboardCharts() {
    const d = this.chartDefaults();

    // Gráfico de linha — Nível 24h
    this.makeChart('chart-line', {
      type: 'line',
      data: {
        labels: HISTORY_24H.labels,
        datasets: [
          {
            label: 'Centro', data: HISTORY_24H.centro,
            borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.06)',
            tension: 0.4, fill: true, borderWidth: 2, pointRadius: 0
          },
          {
            label: 'Norte', data: HISTORY_24H.norte,
            borderColor: '#facc15', backgroundColor: 'rgba(250,204,21,0.04)',
            tension: 0.4, fill: true, borderWidth: 1.5, pointRadius: 0
          },
          {
            label: 'Média', data: HISTORY_24H.media,
            borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.05)',
            tension: 0.4, fill: true, borderWidth: 2, pointRadius: 0
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
          backgroundColor: ['#ef4444','#ef4444','#facc15','#facc15','#22c55e','#facc15','#22c55e','#22c55e'],
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
          backgroundColor: ['#22c55e', '#facc15', '#ef4444'],
          borderColor: '#0f0f0f', borderWidth: 3, hoverOffset: 4
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
          backgroundColor: ['rgba(34,197,94,0.7)', 'rgba(100,116,139,0.5)'],
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
    // Adiciona ponto atual no eixo X
    const now = new Date();
    const label = `${String(now.getHours()).padStart(2,'0')}h`;
    if (chart.data.labels[chart.data.labels.length - 1] !== label) {
      chart.data.labels.push(label);
      chart.data.datasets[0].data.push(this.state.sensors[0].level);
      chart.data.datasets[2].data.push(
        parseFloat((this.state.sensors.filter(x=>x.status!=='offline')
          .reduce((a,x)=>a+x.level,0) / 11).toFixed(1))
      );
      // Mantém janela de 24 pontos
      if (chart.data.labels.length > 24) {
        chart.data.labels.shift();
        chart.data.datasets.forEach(ds => ds.data.shift());
      }
      chart.update('none');
    }
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
    lucide.createIcons();
    this.renderSensorTable();
  },

  /** Filtra, ordena e renderiza as linhas da tabela */
  renderSensorTable() {
    let data = [...this.state.sensors];

    // Filtro de texto
    if (this.state.searchQuery) {
      const q = this.state.searchQuery.toLowerCase();
      data = data.filter(s =>
        s.id.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.bairro.toLowerCase().includes(q) ||
        s.location.toLowerCase().includes(q)
      );
    }

    // Filtro de status
    if (this.state.filterStatus !== 'all') {
      data = data.filter(s => s.status === this.state.filterStatus);
    }

    // Ordenação
    data.sort((a, b) => {
      let va = a[this.state.sortField], vb = b[this.state.sortField];
      if (typeof va === 'string') va = va.toLowerCase(), vb = vb.toLowerCase();
      if (va < vb) return this.state.sortDir === 'asc' ? -1 :  1;
      if (va > vb) return this.state.sortDir === 'asc' ?  1 : -1;
      return 0;
    });

    // Paginação
    const total   = data.length;
    const pages   = Math.ceil(total / this.state.rowsPerPage);
    const start   = (this.state.currentPage - 1) * this.state.rowsPerPage;
    const pageData = data.slice(start, start + this.state.rowsPerPage);

    // Atualiza contagem
    const countEl = document.getElementById('sensor-count');
    if (countEl) countEl.textContent = `${total} sensor${total !== 1 ? 'es' : ''}`;

    // Renderiza linhas
    const tbody = document.getElementById('sensor-tbody');
    if (!tbody) return;
    tbody.innerHTML = pageData.map(s => `
      <tr>
        <td><span class="sensor-id">${s.id}</span></td>
        <td><span class="sensor-name">${s.name}</span></td>
        <td style="color:var(--text-secondary)">${s.bairro}</td>
        <td>
          <span class="sensor-level ${this.getLevelClass(s.status)}">
            ${s.status === 'offline' ? '—' : s.level + ' cm'}
          </span>
        </td>
        <td style="font-family:var(--text-mono)">${s.status === 'offline' ? '—' : s.temp + '°C'}</td>
        <td style="font-family:var(--text-mono)">${s.status === 'offline' ? '—' : s.humidity + '%'}</td>
        <td>${this.getStatusBadge(s.status)}</td>
        <td style="font-family:var(--text-mono);font-size:11px;color:var(--text-muted)">${s.lastRead}</td>
      </tr>
    `).join('');

    // Paginação
    const pgEl = document.getElementById('sensor-pagination');
    if (!pgEl) return;
    pgEl.innerHTML = `
      <span>${start + 1}–${Math.min(start + this.state.rowsPerPage, total)} de ${total}</span>
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
            São Paulo — Rede de Sensores FloodSense AI
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
    lucide.createIcons();

    // Aguarda o DOM renderizar antes de iniciar o Leaflet
    setTimeout(() => this.initLeafletMap(), 100);
  },

  /** Inicializa o mapa Leaflet com tiles escuros e marcadores */
  initLeafletMap() {
    if (!window.L) {
      document.getElementById('leaflet-map').innerHTML =
        '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">Leaflet não carregado. Verifique sua conexão.</div>';
      return;
    }

    // Cria mapa centralizado em SP
    const map = L.map('leaflet-map', {
      center: [-23.5505, -46.6333],
      zoom: 11,
      zoomControl: true,
      attributionControl: true
    });

    // Tiles escuros (CartoDB Dark Matter — compatível com tema do sistema)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© <a href="https://carto.com/">CARTO</a> | FloodSense AI TCC',
      subdomains: 'abcd',
      maxZoom: 18
    }).addTo(map);

    this.state.leafletMap = map;
    this.state.leafletMarkers = [];

    // Adiciona marcadores de cada sensor
    this.state.sensors.forEach(s => {
      const color = s.status === 'critical' ? '#ef4444' :
                    s.status === 'warning'  ? '#facc15' :
                    s.status === 'offline'  ? '#475569' : '#22c55e';

      // Ícone HTML personalizado
      const icon = L.divIcon({
        className: '',
        html: `<div style="
          width:16px;height:16px;border-radius:50%;
          background:${color};
          border:2px solid rgba(255,255,255,0.3);
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
      <div class="map-popup-title">${s.name}</div>
      <div class="map-popup-row"><span>📍 Local</span><span>${s.bairro}</span></div>
      <div class="map-popup-row"><span>💧 Nível</span><span style="color:${statusColor}">${s.status==='offline'?'—':s.level+' cm'}</span></div>
      <div class="map-popup-row"><span>🌡️ Temp.</span><span>${s.status==='offline'?'—':s.temp+'°C'}</span></div>
      <div class="map-popup-row"><span>💦 Umidade</span><span>${s.status==='offline'?'—':s.humidity+'%'}</span></div>
      <div class="map-popup-row"><span>🕐 Leitura</span><span>${s.lastRead}</span></div>
      <div style="margin-top:8px;padding-top:8px;border-top:1px solid #1e293b">
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
  ═════════════════════════════════════════════ */
  renderAI() {
    const root = document.getElementById('app-root');
    const criticals = this.state.sensors.filter(x => x.status === 'critical').length;
    const floodProb = Math.min(99, 60 + criticals * 10 + this.state.sensors.filter(x=>x.status==='warning').length * 4);

    root.innerHTML = `
      <!-- KPIs da IA -->
      <div class="kpi-grid" style="margin-bottom:12px">
        ${[
          { label:'Prob. Enchente (6h)', val: floodProb+'%', color:'col-red', icon:'activity', icls:'ic-red' },
          { label:'Acurácia do Modelo', val: '92%', color:'col-green', icon:'cpu', icls:'ic-green' },
          { label:'F1-Score', val: '0.891', color:'col-blue', icon:'target', icls:'ic-blue' },
          { label:'Latência da IA', val: '1.4s', color:'col-blue', icon:'zap', icls:'ic-blue' }
        ].map((k,i) => `
          <div class="kpi-card kpi-blue" style="animation-delay:${i*0.05}s">
            <div class="kpi-header"><span class="kpi-label">${k.label}</span><div class="kpi-icon ${k.icls}"><i data-lucide="${k.icon}"></i></div></div>
            <div class="kpi-value ${k.color}">${k.val}</div>
          </div>
        `).join('')}
      </div>

      <div class="grid-2" style="margin-bottom:12px">
        <!-- Gráfico: previsão vs real -->
        <div class="chart-card">
          <div class="chart-header">
            <span class="chart-title"><i data-lucide="git-compare"></i> Previsão IA vs Valor Real</span>
            <span class="chart-meta">Últimas 24h</span>
          </div>
          <div class="chart-wrap" style="height:200px"><canvas id="chart-ai-pred"></canvas></div>
          <div class="legend-row">
            <div class="legend-item"><div class="legend-dot" style="background:#38bdf8"></div>Valor Real</div>
            <div class="legend-item"><div class="legend-dot" style="background:#a855f7;border-radius:0"></div>Previsão IA (tracejado)</div>
          </div>
        </div>

        <!-- Comparativo de modelos -->
        <div class="content-card" style="margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="bar-chart-2"></i> Comparação de Modelos</span>
          </div>
          <div style="margin-bottom:16px">
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px">
              Comparativo entre abordagens — mesma base de dados, 5 anos histórico.
            </div>
            <div class="model-compare-row">
              <span class="model-name">Naive Bayes</span>
              <div class="model-bar-wrap"><div class="model-bar progress-fill" style="width:68%;background:var(--text-muted)"></div></div>
              <span class="model-value" style="color:var(--text-muted)">68%</span>
              <span class="model-improve">—</span>
            </div>
            <div class="model-compare-row">
              <span class="model-name">IA Tradicional</span>
              <div class="model-bar-wrap"><div class="model-bar progress-fill" style="width:78%;background:var(--orange)"></div></div>
              <span class="model-value" style="color:var(--orange)">78%</span>
              <span class="model-improve">+10%</span>
            </div>
            <div class="model-compare-row">
              <span class="model-name">Random Forest</span>
              <div class="model-bar-wrap"><div class="model-bar progress-fill" style="width:84%;background:var(--yellow)"></div></div>
              <span class="model-value" style="color:var(--yellow)">84%</span>
              <span class="model-improve">+16%</span>
            </div>
            <div class="model-compare-row">
              <span class="model-name" style="color:var(--blue);font-weight:700">FloodSense AI</span>
              <div class="model-bar-wrap"><div class="model-bar progress-fill" style="width:92%;background:var(--green)"></div></div>
              <span class="model-value" style="color:var(--green)">92%</span>
              <span class="model-improve" style="color:var(--green)">+24% ★</span>
            </div>
          </div>
          <div style="background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.15);border-radius:var(--radius-sm);padding:10px;font-size:11px;color:var(--text-secondary)">
            <strong style="color:var(--green)">✓ Melhoria de 14 pontos percentuais</strong> sobre a IA tradicional (78%), 
            representando uma redução significativa de falsos negativos em eventos de enchente.
          </div>
        </div>
      </div>

      <!-- Gráfico de precisão histórica + parâmetros -->
      <div class="grid-2">
        <div class="chart-card" style="animation-delay:0.2s">
          <div class="chart-header">
            <span class="chart-title"><i data-lucide="trending-up"></i> Precisão Histórica do Modelo</span>
          </div>
          <div class="chart-wrap" style="height:180px"><canvas id="chart-ai-acc"></canvas></div>
        </div>
        <div class="content-card" style="margin-bottom:0;animation-delay:0.25s">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="cpu"></i> Parâmetros do Modelo</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:10px;font-size:12px">
            ${[
              ['Arquitetura', 'LSTM + Random Forest (Ensemble)'],
              ['Features de Entrada', '8 variáveis (nível, temp, umidade, chuva, hora, dia, sazonalidade, solo)'],
              ['Dados de Treino', '5 anos · 260.000 registros históricos'],
              ['Janela Temporal', '24 horas de histórico → previsão 6h'],
              ['Taxa de Atualização', 'A cada 30 minutos (re-treinamento incremental)'],
              ['Framework', 'Python · TensorFlow 2.14 · Scikit-Learn'],
              ['Versão', 'v3.2.1 — Produção (09/2025)']
            ].map(([k, v]) => `
              <div style="display:flex;gap:10px;padding-bottom:8px;border-bottom:1px solid var(--border-3)">
                <span style="color:var(--text-muted);min-width:130px;flex-shrink:0">${k}</span>
                <span style="color:var(--text-secondary)">${v}</span>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
    lucide.createIcons();
    this.initAICharts();
  },

  initAICharts() {
    const d = this.chartDefaults();

    // Previsão vs Real
    this.makeChart('chart-ai-pred', {
      type: 'line',
      data: {
        labels: HISTORY_24H.labels,
        datasets: [
          {
            label: 'Real', data: HISTORY_24H.centro,
            borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.05)',
            tension: 0.4, fill: true, borderWidth: 2, pointRadius: 0
          },
          {
            label: 'Previsão IA',
            data: HISTORY_24H.centro.map((v, i) => parseFloat((v * (0.95 + Math.sin(i) * 0.04)).toFixed(1))),
            borderColor: '#a855f7', backgroundColor: 'transparent',
            tension: 0.4, fill: false, borderWidth: 1.5,
            borderDash: [5, 3], pointRadius: 0
          }
        ]
      },
      options: {
        ...d,
        scales: {
          x: { ...d.scales.x, ticks: { ...d.scales.x.ticks, maxTicksLimit: 8 } },
          y: { ...d.scales.y, ticks: { ...d.scales.y.ticks, callback: v => v + 'cm' } }
        }
      }
    });

    // Acurácia histórica
    this.makeChart('chart-ai-acc', {
      type: 'line',
      data: {
        labels: ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'],
        datasets: [
          {
            label: 'FloodSense AI', data: [85,86,87,88,88,89,90,90,91,91,92,92],
            borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.07)',
            tension: 0.4, fill: true, borderWidth: 2, pointRadius: 3, pointBackgroundColor: '#22c55e'
          },
          {
            label: 'Baseline', data: [74,75,75,76,76,77,77,78,78,78,78,78],
            borderColor: '#475569', backgroundColor: 'transparent',
            tension: 0.4, borderWidth: 1, borderDash: [4, 3], pointRadius: 0
          }
        ]
      },
      options: {
        ...d,
        scales: {
          x: { ...d.scales.x },
          y: { ...d.scales.y, min: 60, max: 100, ticks: { ...d.scales.y.ticks, callback: v => v + '%' } }
        }
      }
    });
  },

  /* ═════════════════════════════════════════════
     11. TELA: ANÁLISE GRÁFICA
  ═════════════════════════════════════════════ */
  renderCharts() {
    const root = document.getElementById('app-root');
    root.innerHTML = `
      <div class="grid-2" style="margin-bottom:12px">
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title"><i data-lucide="trending-up"></i> Nível médio — 7 dias</span></div>
          <div class="chart-wrap" style="height:200px"><canvas id="chart-week"></canvas></div>
        </div>
        <div class="chart-card">
          <div class="chart-header"><span class="chart-title"><i data-lucide="cloud-rain"></i> Precipitação vs Nível</span></div>
          <div class="chart-wrap" style="height:200px"><canvas id="chart-rain"></canvas></div>
        </div>
      </div>
      <div class="grid-2">
        <div class="chart-card" style="animation-delay:0.1s">
          <div class="chart-header"><span class="chart-title"><i data-lucide="bar-chart-3"></i> Alertas por zona — Mês</span></div>
          <div class="chart-wrap" style="height:200px"><canvas id="chart-zone"></canvas></div>
        </div>
        <div class="chart-card" style="animation-delay:0.15s">
          <div class="chart-header"><span class="chart-title"><i data-lucide="radar"></i> Comparação de Modelos</span></div>
          <div class="chart-wrap" style="height:200px"><canvas id="chart-models"></canvas></div>
        </div>
      </div>
    `;
    lucide.createIcons();

    const d = this.chartDefaults();

    this.makeChart('chart-week', {
      type: 'line',
      data: {
        labels: ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'],
        datasets: [{
          data: [48,58,52,66,82,90,72],
          borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.08)',
          tension: 0.4, fill: true, borderWidth: 2,
          pointRadius: 4, pointBackgroundColor: '#38bdf8'
        }]
      },
      options: { ...d, scales: { ...d.scales, y: { ...d.scales.y, ticks: { ...d.scales.y.ticks, callback: v => v+'cm' }, suggestedMin: 0 } } }
    });

    this.makeChart('chart-rain', {
      type: 'bar',
      data: {
        labels: ['00h','03h','06h','09h','12h','15h','18h','21h'],
        datasets: [
          { label: 'Chuva (mm)', data: [5,12,25,18,8,15,30,22], backgroundColor: 'rgba(56,189,248,0.5)', borderRadius: 3, yAxisID: 'y' },
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
          { label: 'Atenção',  data: [4,4,3,3,2,3], backgroundColor: 'rgba(250,204,21,0.7)', borderRadius: 0, stack: 's' },
          { label: 'Normal',   data: [3,5,7,7,10,5], backgroundColor: 'rgba(34,197,94,0.6)', borderRadius: 0, stack: 's' }
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

    this.makeChart('chart-models', {
      type: 'bar',
      data: {
        labels: ['Naive Bayes','SVM','Random\nForest','IA\nTradicional','FloodSense\nAI'],
        datasets: [{
          data: [68, 74, 84, 78, 92],
          backgroundColor: ['#475569','#475569','#facc15','#f97316','#22c55e'],
          borderRadius: 4, borderSkipped: false
        }]
      },
      options: {
        ...d,
        scales: {
          x: { ...d.scales.x, grid: { display: false } },
          y: { ...d.scales.y, min: 50, max: 100, ticks: { ...d.scales.y.ticks, callback: v => v+'%' } }
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
          { label:'Resolvidos Hoje',  val:5,            color:'var(--green)', icon:'✅' }
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
          <button class="btn btn-sm btn-danger" onclick="FloodSense.showToast('info','Defesa Civil','Equipe acionada via sistema.')">
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
    lucide.createIcons();
  },

  /* ═════════════════════════════════════════════
     13. TELA: RELATÓRIOS
  ═════════════════════════════════════════════ */
  renderReports() {
    const root = document.getElementById('app-root');
    root.innerHTML = `
      <div class="grid-2" style="margin-bottom:12px">
        <div class="content-card" style="margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="file-text"></i> Relatórios Disponíveis</span>
          </div>
          ${[
            { icon:'📊', name:'Relatório Diário Completo', meta:'PDF · Sensores, alertas e IA · Hoje', color:'var(--blue-dim)', btn:'pdf' },
            { icon:'📈', name:'Histórico Semanal — Nível Hídrico', meta:'PDF · Gráficos + análise · Últimos 7 dias', color:'var(--blue-dim)', btn:'pdf' },
            { icon:'🤖', name:'Desempenho do Modelo IA', meta:'PDF · Acurácia, F1-Score, matrizes · Mensal', color:'var(--purple-dim)', btn:'pdf' },
            { icon:'📋', name:'Dados Brutos — Sensores', meta:'CSV · Todas as leituras · Exportação raw', color:'var(--green-dim)', btn:'csv' },
            { icon:'🚨', name:'Log de Alertas', meta:'CSV · Histórico completo de alertas', color:'var(--red-dim)', btn:'csv' },
          ].map((r,i) => `
            <div class="report-card" style="animation-delay:${i*0.06}s;background:${r.color}">
              <div class="report-icon" style="background:rgba(255,255,255,0.06);border-radius:var(--radius-sm)">
                <span style="font-size:20px">${r.icon}</span>
              </div>
              <div class="report-info">
                <div class="report-name">${r.name}</div>
                <div class="report-meta">${r.meta}</div>
              </div>
              <button class="btn btn-sm btn-outline report-btn"
                onclick="FloodSense.showToast('info','Download Iniciado','${r.name} gerado com sucesso.')">
                <i data-lucide="download"></i>
                ${r.btn.toUpperCase()}
              </button>
            </div>
          `).join('')}
        </div>
        <div class="content-card" style="margin-bottom:0">
          <div class="content-card-header">
            <span class="content-card-title"><i data-lucide="bar-chart-2"></i> Estatísticas do Período</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:10px">
            ${[
              ['Total de Leituras (hoje)',    '86.400',  'var(--blue)'],
              ['Alertas Emitidos (mês)',       '142',    'var(--red)'],
              ['Tempo Médio de Resposta',      '3.2 min','var(--yellow)'],
              ['Sensores Ativos',              '11/12',  'var(--green)'],
              ['Acurácia Média da IA',         '91.4%',  'var(--green)'],
              ['Eventos Previstos Corretamente','128/139','var(--green)'],
              ['Disponibilidade do Sistema',   '99.7%',  'var(--blue)'],
            ].map(([label, val, color]) => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border-3)">
                <span style="font-size:12px;color:var(--text-secondary)">${label}</span>
                <span style="font-family:var(--text-mono);font-weight:700;color:${color};font-size:13px">${val}</span>
              </div>
            `).join('')}
          </div>
          <div style="margin-top:14px;padding:12px;background:rgba(56,189,248,0.04);border:1px solid rgba(56,189,248,0.12);border-radius:var(--radius-sm);font-size:11px;color:var(--text-secondary)">
            📌 <strong style="color:var(--text-primary)">Nota acadêmica:</strong> Os relatórios em PDF simulam a exportação real. 
            Em produção, o backend gera PDFs via <code style="color:var(--blue)">ReportLab</code> (Python) ou 
            <code style="color:var(--blue)">pdfkit</code> (Node.js).
          </div>
        </div>
      </div>
    `;
    lucide.createIcons();
  },

  /* ═════════════════════════════════════════════
     14. TELA: CONFIGURAÇÕES
  ═════════════════════════════════════════════ */
  renderConfig() {
    const root = document.getElementById('app-root');
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
            ['Nível de Atenção (Amarelo)', '60', 'cm — Monitoramento intensificado'],
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
            ['API Backend (Node.js)', 'online', '● Online · 12ms'],
            ['Firebase Firestore', 'online', '● Sincronizado'],
            ['Modelo IA (Python)', 'online', '● Ativo · v3.2.1'],
            ['Rede IoT (LoRaWAN)', 'warning', '◑ 11/12 sensores'],
            ['API INMET (Clima)', 'online', '● Conectado'],
            ['Defesa Civil API', 'online', '● Integrado · v2.1'],
          ].map(([name, status, label]) => {
            const color = status === 'online' ? 'var(--green)' : status === 'warning' ? 'var(--yellow)' : 'var(--red)';
            const bg    = status === 'online' ? 'rgba(34,197,94,0.08)' : status === 'warning' ? 'rgba(250,204,21,0.08)' : 'rgba(239,68,68,0.08)';
            const border= status === 'online' ? 'rgba(34,197,94,0.15)' : status === 'warning' ? 'rgba(250,204,21,0.15)' : 'rgba(239,68,68,0.15)';
            return `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:${bg};border:1px solid ${border};border-radius:var(--radius-sm);margin-bottom:6px">
              <span style="font-size:12px;color:var(--text-secondary)">${name}</span>
              <span style="font-size:11px;font-family:var(--text-mono);color:${color};font-weight:600">${label}</span>
            </div>`;
          }).join('')}
        </div>
      </div>
    `;
    lucide.createIcons();
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
    const id = `toast-${Date.now()}`;

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

    // Auto-remover após duration ms
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

  /** Inicia o relógio em tempo real */
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

/* ═══════════════════════════════════════════════════════════════════
   17. INICIALIZAÇÃO
   Executa após o DOM estar completamente carregado.
═══════════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  // Renderiza ícones Lucide na tela de login
  lucide.createIcons();

  // Define configurações globais padrão do Chart.js
  Chart.defaults.font.family = "'Space Grotesk', system-ui, sans-serif";
  Chart.defaults.color = '#475569';
  Chart.defaults.borderColor = 'rgba(30,41,59,0.5)';

  console.log(
    '%c FloodSense AI v3.0 ',
    'background:#38bdf8;color:#000;font-weight:bold;padding:4px 8px;border-radius:4px',
    '\nTCC — Sistemas de Informação',
    '\nCredenciais demo: admin@floodsense.ai / floodsense2025'
  );
});
