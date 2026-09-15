/*
  ╔══════════════════════════════════════════════════════════════════╗
  ║   FloodSense AI — Firmware do Sensor (Protótipo FS-001)          ║
  ║   Placa: ESP32 DevKit                                            ║
  ║   Sensor: HC-SR04 ou JSN-SR04T (ultrassônico)                    ║
  ║                                                                    ║
  ║   O que este código faz:                                         ║
  ║   1. Conecta no Wi-Fi                                            ║
  ║   2. Mede a distância até a água a cada 3 segundos               ║
  ║   3. Calcula o nível de água (cm) e o status (normal/warning/    ║
  ║      critical)                                                    ║
  ║   4. Envia tudo pro Firebase Realtime Database via HTTP REST     ║
  ╚══════════════════════════════════════════════════════════════════╝
*/

#include <WiFi.h>
#include <HTTPClient.h>

// ─────────────────────────────────────────────────────────────
// 1. CONFIGURAÇÃO — edite estes valores antes de gravar
// ─────────────────────────────────────────────────────────────

const char* WIFI_SSID     = "NOME-WIFI";
const char* WIFI_PASSWORD = "SUA_SENHA_AQUI";

// URL do seu Realtime Database, SEM "https://" e SEM barra final.
// Exemplo: "floodsense-ai-tcc-default-rtdb.firebaseio.com"
const char* FIREBASE_HOST = "SEU-PROJETO-default-rtdb.firebaseio.com";

// ID do sensor (mantém FS-001 pra bater com o dashboard)
const char* SENSOR_ID = "FS-001";

// Altura do sensor até o fundo do ponto de medição (cm).
// nivel_agua = SENSOR_HEIGHT_CM - distancia_medida
const float SENSOR_HEIGHT_CM = 150.0;

// Limites de status (mesma lógica do dashboard em script.js)
const float LIMIT_WARNING  = 60.0;  // cm
const float LIMIT_CRITICAL = 90.0;  // cm

// Pinos do ultrassônico
const int PIN_TRIG = 5;
const int PIN_ECHO = 18;

// Intervalo entre leituras (ms) — igual ao polling do dashboard (3s)
const unsigned long READ_INTERVAL_MS = 3000;

// ─────────────────────────────────────────────────────────────
// 2. ESTADO
// ─────────────────────────────────────────────────────────────
unsigned long lastReadTime = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);

  connectWiFi();
}

void loop() {
  // Mantém o Wi-Fi vivo
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  unsigned long now = millis();
  if (now - lastReadTime >= READ_INTERVAL_MS) {
    lastReadTime = now;

    float distancia = medirDistanciaCm();

    if (distancia < 0) {
      Serial.println("[FloodSense] Falha na leitura do sensor (fora de alcance).");
      return;
    }

    float nivel = SENSOR_HEIGHT_CM - distancia;
    if (nivel < 0) nivel = 0;

    String status = calcularStatus(nivel);

    Serial.printf(
      "[FloodSense] Distancia: %.1f cm | Nivel: %.1f cm | Status: %s\n",
      distancia, nivel, status.c_str()
    );

    enviarParaFirebase(nivel, status);
  }
}

// ─────────────────────────────────────────────────────────────
// 3. WI-FI
// ─────────────────────────────────────────────────────────────
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
    Serial.println("\n[FloodSense] Wi-Fi conectado! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[FloodSense] Falha ao conectar Wi-Fi. Tentando de novo no próximo loop.");
  }
}

// ─────────────────────────────────────────────────────────────
// 4. LEITURA DO SENSOR ULTRASSÔNICO
//    Faz 3 leituras e usa a mediana pra reduzir ruído
// ─────────────────────────────────────────────────────────────
float medirDistanciaCm() {
  float leituras[3];

  for (int i = 0; i < 3; i++) {
    leituras[i] = leituraUnica();
    delay(60);
  }

  // Ordena as 3 leituras (bubble sort simples) e pega a mediana
  for (int i = 0; i < 2; i++) {
    for (int j = 0; j < 2 - i; j++) {
      if (leituras[j] > leituras[j + 1]) {
        float tmp = leituras[j];
        leituras[j] = leituras[j + 1];
        leituras[j + 1] = tmp;
      }
    }
  }

  return leituras[1]; // mediana
}

float leituraUnica() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  // Timeout de 30ms (~5m de alcance) evita travar se não houver eco
  long duracao = pulseIn(PIN_ECHO, HIGH, 30000);

  if (duracao == 0) return -1; // sem leitura

  // Distância (cm) = duração * velocidade do som / 2
  float distancia = duracao * 0.0343 / 2.0;
  return distancia;
}

// ─────────────────────────────────────────────────────────────
// 5. STATUS (mesma regra usada no script.js do dashboard)
// ─────────────────────────────────────────────────────────────
String calcularStatus(float nivel) {
  if (nivel >= LIMIT_CRITICAL) return "critical";
  if (nivel >= LIMIT_WARNING)  return "warning";
  return "normal";
}

// ─────────────────────────────────────────────────────────────
// 6. ENVIO PARA O FIREBASE (REST — PATCH em /sensors/FS-001.json)
// ─────────────────────────────────────────────────────────────
void enviarParaFirebase(float nivel, String status) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;

  String url = "https://" + String(FIREBASE_HOST) + "/sensors/" + String(SENSOR_ID) + ".json";

  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  // Horário (o ESP32 não tem RTC configurado por padrão — aqui mandamos
  // só o nível/status; o dashboard usa o horário local do navegador
  // como lastRead se este campo vier vazio. Se quiser horário real,
  // configure NTP com configTime()).
  String payload = "{";
  payload += "\"level\":" + String(nivel, 1) + ",";
  payload += "\"status\":\"" + status + "\"";
  payload += "}";

  int httpCode = http.PATCH(payload);

  if (httpCode > 0) {
    Serial.printf("[FloodSense] Enviado ao Firebase (HTTP %d)\n", httpCode);
  } else {
    Serial.printf("[FloodSense] Erro ao enviar: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
}
