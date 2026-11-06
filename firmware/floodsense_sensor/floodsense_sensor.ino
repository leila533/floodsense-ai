#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>
#include <math.h>

#include "secrets.h"  // Wi-Fi e credenciais do Firebase (fora do Git)

const char* FIREBASE_HOST =
    "floodsense-ai-7a6b9-default-rtdb.firebaseio.com";

const char* SENSOR_ID = "FS-001";

// Caminho do histórico operacional usado pelo serviço de previsão.
// Não renomear sem atualizar previsao_floodsense_corrigido.py.
const char* HISTORY_TRAINING_PATH = "/sensor_history_treinamento";

// nível = altura do ponto de medição − distância medida
const float SENSOR_HEIGHT_CM = 45.0;

const float LIMIT_WARNING  = 60.0;
const float LIMIT_CRITICAL = 90.0;

const int PIN_TRIG = 5;
const int PIN_ECHO = 18;

// Variação aceita sem confirmação = base + taxa × minutos desde a
// última leitura aceita. Valores iniciais: calibrar com os dados.
const float LIMITE_BASE_CM         = 5.0;
const float LIMITE_TAXA_CM_POR_MIN = 15.0;

// Mudança fora do limite só é aceita se se repetir em leituras
// seguidas dentro desta tolerância.
const float TOLERANCIA_CONFIRMACAO_CM = 5.0;
const int   CONFIRMACOES_NECESSARIAS  = 3;

// Acima deste tempo sem leitura aceita, a referência é antiga.
const float MAX_TEMPO_REFERENCIA_MIN = 2.0;

const unsigned long READ_INTERVAL_MS     = 3000;   // leitura / dashboard
const unsigned long HISTORY_INTERVAL_MS  = 60000;  // histórico da IA (1 min)
const unsigned long RECONEXAO_WIFI_MS    = 15000;  // nova tentativa de Wi-Fi

// Leitura válida mais antiga que isso não é gravada no histórico.
const unsigned long MAX_IDADE_LEITURA_MS = 10000;

// Timeout das requisições HTTP.
const unsigned long HTTP_TIMEOUT_MS = 5000;

// Token do Firebase dura 1 hora; renovamos antes disso.
const unsigned long TOKEN_VALIDADE_MS = 50UL * 60UL * 1000UL;

const char* NTP_SERVER = "pool.ntp.org";
const long  GMT_OFFSET_SEC      = -3 * 3600;
const int   DAYLIGHT_OFFSET_SEC = 0;

unsigned long lastReadTime        = 0;
unsigned long lastHistoryTime     = 0;
unsigned long ultimaTentativaWiFi = 0;

// Token de acesso do dispositivo ao Firebase
String idToken = "";
unsigned long tokenMillis = 0;

// Último nível VÁLIDO (−1 = nenhum ainda)
float ultimoNivel = -1;
unsigned long ultimoNivelMillis = 0;

// Candidato a novo nível, aguardando confirmação
float candidato = -1;
int   contCandidato = 0;

void setup() {

  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("==============================================");
  Serial.println("       FloodSense AI - FS-001  (v5)");
  Serial.println("==============================================");

  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);

  WiFi.setAutoReconnect(true);
  connectWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
    Serial.println("[FloodSense] Sincronizando horario...");
    delay(1500);
    mostrarHorario();
    garantirToken();
  }

  Serial.println();
  Serial.println("[FloodSense] Sistema iniciado.");
  Serial.println("[FloodSense] Firmware: HISTORICO DE TREINAMENTO (v5)");
  Serial.printf("[FloodSense] Leitura atual: %lu ms\n", READ_INTERVAL_MS);
  Serial.printf("[FloodSense] Variacao aceita: %.1f cm + %.1f cm/min\n",
                LIMITE_BASE_CM, LIMITE_TAXA_CM_POR_MIN);
  Serial.print("[FloodSense] Caminho do historico: ");
  Serial.print(HISTORY_TRAINING_PATH);
  Serial.print("/");
  Serial.println(SENSOR_ID);
  Serial.println();
}

void loop() {

  garantirWiFi();

  unsigned long now = millis();

  // leitura atual
  if (now - lastReadTime >= READ_INTERVAL_MS) {

    lastReadTime = now;

    float distancia = medirDistanciaCm();

    if (distancia < 0) {
      Serial.println("[FloodSense] Falha na leitura do sensor.");

    } else {

      float nivel = SENSOR_HEIGHT_CM - distancia;
      if (nivel < 0) {
        nivel = 0;
      }

      if (aceitarLeitura(nivel)) {

        String status = calcularStatus(nivel);

        Serial.println();
        Serial.println("----------------------------------------------");
        Serial.printf("[FloodSense] Distancia: %.1f cm\n", distancia);
        Serial.printf("[FloodSense] Nivel: %.1f cm\n", nivel);
        Serial.printf("[FloodSense] Status: %s\n", status.c_str());

        enviarParaFirebase(distancia, nivel, status);
      }
    }
  }

  // histórico para a IA (só com leitura válida e recente)
  if (ultimoNivel >= 0 && now - lastHistoryTime >= HISTORY_INTERVAL_MS) {

    lastHistoryTime = now;

    if (millis() - ultimoNivelMillis > MAX_IDADE_LEITURA_MS) {
      Serial.println("[FloodSense] Ultima leitura valida e antiga; "
                     "historico NAO gravado.");
    } else {
      Serial.println();
      Serial.println("[FloodSense] Salvando leitura no HISTORICO DE TREINAMENTO...");
      salvarHistorico(ultimoNivel);
    }
  }
}

// Retorna true se a leitura deve ser usada.
//  - Dentro da variação permitida (base + taxa × minutos): aceita.
//  - Fora dela: só aceita após CONFIRMACOES_NECESSARIAS leituras
//    seguidas dentro da tolerância entre si.

bool aceitarLeitura(float nivel) {

  if (ultimoNivel < 0) {
    confirmarLeitura(nivel);
    return true;
  }

  float minutos = (millis() - ultimoNivelMillis) / 60000.0;
  bool referenciaValida = minutos <= MAX_TEMPO_REFERENCIA_MIN;
  float variacaoPermitida = LIMITE_BASE_CM + LIMITE_TAXA_CM_POR_MIN * minutos;

  if (referenciaValida && fabs(nivel - ultimoNivel) <= variacaoPermitida) {
    confirmarLeitura(nivel);
    return true;
  }

  if (contCandidato > 0 &&
      fabs(nivel - candidato) <= TOLERANCIA_CONFIRMACAO_CM) {
    contCandidato++;
  } else {
    contCandidato = 1;
  }
  candidato = nivel;

  if (contCandidato >= CONFIRMACOES_NECESSARIAS) {
    Serial.printf("[FloodSense] Mudanca confirmada em %d leituras seguidas; aceita.\n",
                  contCandidato);
    confirmarLeitura(nivel);
    return true;
  }

  Serial.printf("[FloodSense] Leitura %.1f cm descartada (%d de %d para confirmar).\n",
                nivel, contCandidato, CONFIRMACOES_NECESSARIAS);
  return false;
}

void confirmarLeitura(float nivel) {
  ultimoNivel = nivel;
  ultimoNivelMillis = millis();
  contCandidato = 0;
}

// Conexão inicial, no setup. Espera até 15 s.
void connectWiFi() {

  Serial.print("[FloodSense] Conectando ao Wi-Fi");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED && tentativas < 30) {
    delay(500);
    Serial.print(".");
    tentativas++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("[FloodSense] Wi-Fi conectado!");
    Serial.print("[FloodSense] IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("[FloodSense] Falha ao conectar.");
  }
}

// Reconexão sem bloquear: chamada a cada passagem do loop.
void garantirWiFi() {

  static bool estavaConectado = true;

  if (WiFi.status() == WL_CONNECTED) {
    if (!estavaConectado) {
      Serial.println("[FloodSense] Wi-Fi reconectado.");
      configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
      estavaConectado = true;
    }
    return;
  }

  if (estavaConectado) {
    Serial.println("[FloodSense] Wi-Fi caiu. Leituras continuam; tentando reconectar.");
    estavaConectado = false;
  }

  unsigned long agora = millis();
  if (agora - ultimaTentativaWiFi < RECONEXAO_WIFI_MS) {
    return;
  }

  ultimaTentativaWiFi = agora;
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

// Renova o token quando ele não existe ou está perto de expirar.

bool garantirToken() {

  if (idToken.length() > 0 && millis() - tokenMillis < TOKEN_VALIDADE_MS) {
    return true;
  }

  return obterTokenFirebase();
}

bool obterTokenFirebase() {

  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;

  String url =
      "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" +
      String(FIREBASE_API_KEY);

  http.begin(url);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");

  String payload =
      "{\"email\":\"" + String(DEVICE_EMAIL) +
      "\",\"password\":\"" + String(DEVICE_PASSWORD) +
      "\",\"returnSecureToken\":true}";

  int httpCode = http.POST(payload);

  if (httpCode != 200) {
    Serial.printf("[FloodSense] Falha no login do dispositivo: HTTP %d\n", httpCode);
    http.end();
    idToken = "";
    return false;
  }

  String corpo = http.getString();
  http.end();

  idToken = extrairCampo(corpo, "idToken");
  tokenMillis = millis();

  if (idToken.length() == 0) {
    Serial.println("[FloodSense] Resposta do login sem token.");
    return false;
  }

  Serial.println("[FloodSense] Login do dispositivo no Firebase: OK.");
  return true;
}

// Extrai o valor de um campo de texto de uma resposta JSON simples.
String extrairCampo(const String& corpo, const String& campo) {

  String chave = "\"" + campo + "\"";

  int i = corpo.indexOf(chave);
  if (i < 0) return "";

  int dp = corpo.indexOf(':', i + chave.length());
  if (dp < 0) return "";

  int a = corpo.indexOf('"', dp + 1);
  if (a < 0) return "";

  int b = corpo.indexOf('"', a + 1);
  if (b < 0) return "";

  return corpo.substring(a + 1, b);
}

// Monta a URL do Firebase com o token. "caminho" já inclui ".json".
String urlFirebase(const String& caminho) {
  return "https://" + String(FIREBASE_HOST) + caminho + "?auth=" + idToken;
}

// Mediana de 3 leituras. Retorna -1 se a leitura falhar.
float medirDistanciaCm() {

  float leituras[3];

  for (int i = 0; i < 3; i++) {
    leituras[i] = leituraUnica();
    delay(60);
  }

  // Ordenação simples (3 elementos)
  for (int i = 0; i < 2; i++) {
    for (int j = 0; j < 2 - i; j++) {
      if (leituras[j] > leituras[j + 1]) {
        float tmp = leituras[j];
        leituras[j] = leituras[j + 1];
        leituras[j + 1] = tmp;
      }
    }
  }

  return leituras[1];
}

float leituraUnica() {

  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  long duracao = pulseIn(PIN_ECHO, HIGH, 30000);

  if (duracao == 0) {
    return -1;
  }

  return duracao * 0.0343 / 2.0;
}

String calcularStatus(float nivel) {

  if (nivel >= LIMIT_CRITICAL) {
    return "critical";
  }

  if (nivel >= LIMIT_WARNING) {
    return "warning";
  }

  return "normal";
}

// Caminho: /sensors/FS-001 (PATCH)

void enviarParaFirebase(float distancia, float nivel, String status) {

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  if (!garantirToken()) {
    return;
  }

  HTTPClient http;

  String url = urlFirebase("/sensors/" + String(SENSOR_ID) + ".json");

  http.begin(url);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");

  String payload = "{";
  payload += "\"id\":\"" + String(SENSOR_ID) + "\",";
  payload += "\"distance\":" + String(distancia, 1) + ",";
  payload += "\"level\":" + String(nivel, 1) + ",";
  payload += "\"status\":\"" + status + "\"";
  payload += "}";

  int httpCode = http.PATCH(payload);

  if (httpCode == 401) {
    idToken = "";  // força novo login na próxima vez
  }

  if (httpCode > 0) {
    Serial.printf("[FloodSense] Firebase atual HTTP %d\n", httpCode);
  } else {
    Serial.printf("[FloodSense] Erro Firebase: %s\n",
                  http.errorToString(httpCode).c_str());
  }

  http.end();
}

// Caminho: /sensor_history_treinamento/FS-001/<timestamp> (PUT)
// Formato: { "timestamp": 1780000000, "level": 58.4 }

void salvarHistorico(float nivel) {

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  time_t agora;
  time(&agora);

  if (agora < 100000) {
    Serial.println("[FloodSense] Horario NTP ainda nao sincronizado.");
    return;
  }

  if (!garantirToken()) {
    return;
  }

  HTTPClient http;

  String timestamp = String((unsigned long) agora);

  String caminho =
      String(HISTORY_TRAINING_PATH) + "/" +
      String(SENSOR_ID) + "/" + timestamp + ".json";

  String url = urlFirebase(caminho);

  Serial.print("[FloodSense] Destino: ");
  Serial.println(caminho);

  http.begin(url);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");

  String payload = "{";
  payload += "\"timestamp\":" + timestamp + ",";
  payload += "\"level\":" + String(nivel, 1);
  payload += "}";

  int httpCode = http.PUT(payload);

  if (httpCode == 401) {
    idToken = "";  // força novo login na próxima vez
  }

  if (httpCode > 0) {
    Serial.printf("[FloodSense] Historico TREINAMENTO salvo "
                  "HTTP %d | timestamp %s | nivel %.1f cm\n",
                  httpCode, timestamp.c_str(), nivel);
  } else {
    Serial.printf("[FloodSense] Erro ao salvar HISTORICO DE TREINAMENTO: %s\n",
                  http.errorToString(httpCode).c_str());
  }

  http.end();
}

void mostrarHorario() {

  struct tm timeinfo;

  if (!getLocalTime(&timeinfo, 2000)) {
    Serial.println("[FloodSense] Nao foi possivel obter horario.");
    return;
  }

  char horario[30];
  strftime(horario, sizeof(horario), "%d/%m/%Y %H:%M:%S", &timeinfo);

  Serial.print("[FloodSense] Horario: ");
  Serial.println(horario);
}
