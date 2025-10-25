#include <WiFi.h>
#include <WebSocketsClient.h>
#include "driver/i2s.h"
#include <math.h>
#include <WiFiManager.h>  
#include <Preferences.h>
#include <WebServer.h>
#include <queue>
#include <vector>

// ======================================================
// ================ WEBSOCKET CONFIGURATION ==============
// ======================================================

String websocket_host = "192.168.1.6";   // WebSocket server IP or hostname
const int websocket_port = 1969;         // WebSocket server port
const char* websocket_path = "/";        // WebSocket endpoint path

Preferences prefs;                       // Non-volatile preferences storage
WebSocketsClient webSocket;              // WebSocket client instance

const char* PREF_NAMESPACE = "myapp";    // Preferences namespace
const char* PREF_KEY_SERVER = "server";  // Key for saved server address

// ======================================================
// ================== AUDIO QUEUE CONFIG =================
// ======================================================

std::queue<std::vector<uint8_t>> audioQueue;  // Fila para áudio
const size_t MAX_QUEUE_SIZE = 30;             // Aumentado para mais capacidade
SemaphoreHandle_t audioQueueMutex;            // Mutex para thread safety
TaskHandle_t audioSendTaskHandle = NULL;      // Handle da task de envio

// Variáveis para controle de fluxo
bool wakeBufferSending = false;               // Se está enviando wake buffer
int wakeBufferSendIndex = 0;                  // Índice atual do wake buffer
const size_t WAKE_BUFFER_CHUNK_SIZE = 1024;   // Tamanho do chunk para wake buffer

// ======================================================
// ================== AUDIO PARAMETERS ===================
// ======================================================

const int SAMPLE_RATE = 16000;           // Sample rate for audio recording and playback
const int PRE_WAKE_SECONDS = 0.5;        // Audio duration (in seconds) before wake word
const int POST_WAKE_SECONDS = 1.5;       // Audio duration (in seconds) after wake word
const unsigned long MIN_RECORD_MS = 300; // Minimum recording duration (milliseconds)
const unsigned long MAX_RECORD_MS = 15000; // Maximum recording duration (milliseconds)
const unsigned long SILENCE_TIMEOUT_MS = 1500; // Timeout for silence detection (milliseconds)

const uint8_t endMarker[4] = {0xFF, 0xFF, 0xFF, 0xFF}; // Marker to signal end of data transmission

const int QAKE_WORD = 1000;              // Wake word detection tone frequency (Hz)

// ===== Signal processing parameters =====
const float alpha = 0.3;                 // Envelope smoothing factor (RMS/ENV filter)
const float alphaNoise = 0.05;           // Noise envelope smoothing factor
static float env = 0.0f;                 // Current audio envelope value
static float envNoise = 0.1;             // Average background noise level

uint32_t capturedSamples = 0;            // Total number of captured samples

static float volume = 1.0;

// ======================================================
// ==================== I2S CONFIGURATION ================
// ======================================================

// ---- Microphone I2S port (input) ----
#define I2S_MIC_PORT I2S_NUM_0
#define I2S_MIC_WS   33   // L/R clock (word select)
#define I2S_MIC_SD   32   // Serial data input
#define I2S_MIC_SCK  14   // Serial clock

// ---- Speaker I2S port (output) ----
#define I2S_SPEAKER_PORT I2S_NUM_1
#define I2S_SPEAKER_DOUT 22  // Serial data output
#define I2S_SPEAKER_BCLK 19  // Bit clock
#define I2S_SPEAKER_LRC  21  // Left/right clock


// ======================================================
// ==================== SYSTEM STATES ====================
// ======================================================

bool sendingWakeBuffer = false;  // True when sending pre-wake audio buffer
bool recording = false;          // True when actively recording audio
bool waitingResponse = false;    // True when waiting for server response
bool receivingAudio = false;     // True when receiving audio from server
bool headerSkipped = false;      // True if WAV header has been skipped (for playback)

unsigned long recordStart = 0;   // Timestamp when recording started
unsigned long lastSound = 0;     // Timestamp of the last detected sound


// ======================================================
// ================= WAKE BUFFER (1 second) ==============
// ======================================================

const int wakeBufferSamples = SAMPLE_RATE; // 1 second buffer at 16kHz
int16_t wakeBuffer[wakeBufferSamples];     // Circular buffer for pre-wake audio
int wakeBufferIndex = 0;                   // Current index in the wake buffer

// ====== PROTÓTIPOS ======
void setup_i2s_microphone();
void setup_i2s_speaker();
void captureAudio();
void connectWiFiManager();
void playBeep(float frequency, int duration_ms);
void beepReady();
void beepEndRecording();
void audioSendTask(void *parameter);
bool addToAudioQueue(const uint8_t* data, size_t length);
void sendWakeBufferToQueue();
void clearAudioQueue();
void sendWakeBufferInChunks(); // Nova função para enviar wake buffer em chunks

void saveServerToPrefs(const String &s) {
  prefs.begin(PREF_NAMESPACE, false);
  prefs.putString(PREF_KEY_SERVER, s);
  prefs.end();
}

String readServerFromPrefs() {
  prefs.begin(PREF_NAMESPACE, true);
  String s = prefs.getString(PREF_KEY_SERVER, "");
  prefs.end();
  return s;
}

// ====== CONFIG I2S ======
void setup_i2s_microphone() {
  const i2s_config_t cfg = {
      .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
      .sample_rate = SAMPLE_RATE,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
      .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
      .dma_buf_count = 8,
      .dma_buf_len = 512,
      .use_apll = true
  };

  const i2s_pin_config_t pin_cfg = {
      .mck_io_num = I2S_PIN_NO_CHANGE,
      .bck_io_num = I2S_MIC_SCK,
      .ws_io_num = I2S_MIC_WS,
      .data_out_num = I2S_PIN_NO_CHANGE,
      .data_in_num = I2S_MIC_SD
  };

  i2s_driver_install(I2S_MIC_PORT, &cfg, 0, NULL);
  i2s_set_pin(I2S_MIC_PORT, &pin_cfg);
  i2s_set_clk(I2S_MIC_PORT, SAMPLE_RATE, I2S_BITS_PER_SAMPLE_32BIT, I2S_CHANNEL_MONO);
  Serial.println("[I2S] 🎤 Microfone configurado");
}

void setup_i2s_speaker() {
  const i2s_config_t cfg = {
      .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
      .sample_rate = SAMPLE_RATE,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
      .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
      .dma_buf_count = 8,
      .dma_buf_len = 512,
      .use_apll = false,
      .tx_desc_auto_clear = true
  };

  const i2s_pin_config_t pin_cfg = {
      .mck_io_num = I2S_PIN_NO_CHANGE,
      .bck_io_num = I2S_SPEAKER_BCLK,
      .ws_io_num = I2S_SPEAKER_LRC,
      .data_out_num = I2S_SPEAKER_DOUT,
      .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_SPEAKER_PORT, &cfg, 0, NULL);
  i2s_set_pin(I2S_SPEAKER_PORT, &pin_cfg);
  Serial.println("[I2S] 🔊 Alto-falante configurado");
}

// ====== TASK DE ENVIO DE ÁUDIO (NÃO BLOQUEANTE) ======
void audioSendTask(void *parameter) {
  while (true) {
    if (webSocket.isConnected()) {
      // Verificar se há dados na fila para enviar
      if (xSemaphoreTake(audioQueueMutex, portMAX_DELAY)) {
        if (!audioQueue.empty()) {
          std::vector<uint8_t> audio_data = audioQueue.front();
          audioQueue.pop();
          xSemaphoreGive(audioQueueMutex);
          
          // Enviar de forma não-bloqueante
          webSocket.sendBIN(audio_data.data(), audio_data.size());
          
          // Pequeno delay para evitar sobrecarga da rede
          vTaskDelay(2 / portTICK_PERIOD_MS);
        } else {
          xSemaphoreGive(audioQueueMutex);
        }
      }
    } else {
      // Se não conectado, dar mais tempo para outras tasks
      vTaskDelay(50 / portTICK_PERIOD_MS);
    }
    
    vTaskDelay(5 / portTICK_PERIOD_MS); // Delay reduzido para melhor responsividade
  }
}

// ====== ADICIONAR À FILA DE ÁUDIO ======
bool addToAudioQueue(const uint8_t* data, size_t length) {
  if (xSemaphoreTake(audioQueueMutex, portMAX_DELAY)) {
    bool success = false;
    
    if (audioQueue.size() < MAX_QUEUE_SIZE) {
      std::vector<uint8_t> packet(data, data + length);
      audioQueue.push(packet);
      success = true;
    } else {
      // Fila cheia - não descartar imediatamente, vamos tentar estratégias diferentes
      success = false;
    }
    
    xSemaphoreGive(audioQueueMutex);
    return success;
  }
  return false;
}

// ====== ADICIONAR À FILA COM ESTRATÉGIA INTELIGENTE ======
bool addToAudioQueueSmart(const uint8_t* data, size_t length, bool isHighPriority = false) {
  if (xSemaphoreTake(audioQueueMutex, portMAX_DELAY)) {
    bool success = false;
    
    if (audioQueue.size() < MAX_QUEUE_SIZE) {
      std::vector<uint8_t> packet(data, data + length);
      audioQueue.push(packet);
      success = true;
    } else if (isHighPriority) {
      // Para alta prioridade, remover o mais antigo se necessário
      if (!audioQueue.empty()) {
        audioQueue.pop();
        std::vector<uint8_t> packet(data, data + length);
        audioQueue.push(packet);
        success = true;
        Serial.println("[QUEUE] 🔄 Pacote antigo removido para prioridade alta");
      }
    }
    
    xSemaphoreGive(audioQueueMutex);
    return success;
  }
  return false;
}

// ====== LIMPAR FILA ======
void clearAudioQueue() {
  if (xSemaphoreTake(audioQueueMutex, portMAX_DELAY)) {
    while (!audioQueue.empty()) {
      audioQueue.pop();
    }
    wakeBufferSending = false;
    wakeBufferSendIndex = 0;
    xSemaphoreGive(audioQueueMutex);
  }
}

// ====== ENVIAR WAKE BUFFER EM CHUNKS INTELIGENTES ======
void sendWakeBufferInChunks() {
  if (!wakeBufferSending) {
    // Iniciar envio do wake buffer
    wakeBufferSending = true;
    wakeBufferSendIndex = 0;
    Serial.println("[MIC] 🚀 Iniciando envio do wake buffer em chunks...");
    webSocket.sendTXT("wake_buffer_start");
  }

  // Enviar alguns chunks por vez, baseado no espaço disponível na fila
  int chunksToSend = 3; // Número máximo de chunks por iteração
  int chunksSent = 0;

  while (chunksSent < chunksToSend && wakeBufferSendIndex < wakeBufferSamples) {
    size_t remaining = wakeBufferSamples - wakeBufferSendIndex;
    size_t chunkSize = min(WAKE_BUFFER_CHUNK_SIZE, remaining);
    
    int startIdx = (wakeBufferIndex + wakeBufferSendIndex + 1) % wakeBufferSamples;
    
    // Verificar espaço na fila antes de adicionar
    if (xSemaphoreTake(audioQueueMutex, 0) == pdTRUE) {
      int availableSlots = MAX_QUEUE_SIZE - audioQueue.size();
      xSemaphoreGive(audioQueueMutex);
      
      if (availableSlots > 2) { // Manter pelo menos 2 slots livres
        if (addToAudioQueueSmart((uint8_t*)&wakeBuffer[startIdx], chunkSize * sizeof(int16_t), true)) {
          wakeBufferSendIndex += chunkSize;
          chunksSent++;
        } else {
          break; // Não conseguiu adicionar, sair do loop
        }
      } else {
        break; // Pouco espaço disponível, tentar na próxima iteração
      }
    } else {
      break; // Não conseguiu pegar o mutex, tentar depois
    }
  }

  // Verificar se terminou o wake buffer
  if (wakeBufferSendIndex >= wakeBufferSamples) {
    wakeBufferSending = false;
    wakeBufferSendIndex = 0;
    sendingWakeBuffer = true;
    capturedSamples = 0;
    Serial.printf("[MIC] ✅ Wake buffer completo enviado: %d samples\n", wakeBufferSamples);
  }
}

// ====== CAPTURA ======
void captureAudio() {
  const size_t bufSize = 512;
  int32_t s32[bufSize];
  int16_t s16[bufSize];
  size_t bytesRead = 0;

  // === 1. Captura amostra do microfone ===
  size_t samplesRead = readMicSamples(s32, bufSize, bytesRead);

  // === 2. Atualiza RMS e envelope ===
  float rms = calculateRMS(s32, samplesRead);
  updateEnvelopes(rms);

  // === 3. Calcula limiares dinâmicos ===
  float dynamicThreshold, dynamicSilenceThreshold;
  computeThresholds(dynamicThreshold, dynamicSilenceThreshold);

  // === 4. Converte 32→16 bits e atualiza buffer circular ===
  convertAndStoreSamples(s32, s16, samplesRead);

  // === 5. Gerenciar envio do wake buffer em chunks ===
  if (wakeBufferSending) {
    sendWakeBufferInChunks();
  }
  
  // === 6. Iniciar envio do wake buffer se detectou som ===
  else if (shouldSendWakeBuffer(dynamicThreshold)) {
    sendWakeBufferInChunks(); // Inicia o processo
  }

  // === 7. Envio de áudio pós-wake ===
  if (sendingWakeBuffer && !wakeBufferSending) {
    sendPostWakeAudio(s16, samplesRead);
  }

  // === 8. Envio de áudio contínuo (modo gravação) ===
  if (recording) {
    sendContinuousAudio(s16, samplesRead, dynamicSilenceThreshold);
  }
}

// ====== EVENTOS WEBSOCKET ======
void webSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      Serial.println("[WS] ✅ Conectado");
      playBeep(1000, 150);
      break;

    case WStype_TEXT:
      Serial.printf("[WS] 📩 Texto: %s\n", payload);

      if (strcmp((char*)payload, "wake_word_detected") == 0) {
        Serial.println("[WS] 🎤 Wake word confirmada! Gravando...");
        webSocket.sendTXT("start_audio");
        beepReady();
        delay(500);
        sendingWakeBuffer = false;
        recording = true;
        recordStart = millis();
        lastSound = millis();
        // Parar envio do wake buffer se ainda estiver acontecendo
        wakeBufferSending = false;
      } 
      else if (strcmp((char*)payload, "wake_word_rejected") == 0) {
        Serial.println("[WS] 🎤 Wake word rejeitada!");
        sendingWakeBuffer = false;
        recording = false;
        wakeBufferSending = false;
        clearAudioQueue(); // Limpar fila se wake word foi rejeitada
      } 
      else if (length >= strlen("set_volume:") && 
              strncmp((char*)payload, "set_volume:", strlen("set_volume:")) == 0) {

        const char* valueStr = (char*)payload + strlen("set_volume:");
        Serial.printf("🎚️ Comando de volume recebido: %s\n", valueStr);

        // Remove espaços e quebras de linha, se houver
        while (*valueStr == ' ' || *valueStr == '\n' || *valueStr == '\r') valueStr++;

        if (valueStr[0] == '+') {
          volume = constrain(volume + 0.3f, 0.0f, 1.0f);
          Serial.printf("🔊 Volume aumentado para %.2f\n", volume);
        } 
        else if (valueStr[0] == '-') {
          volume = constrain(volume - 0.3f, 0.0f, 1.0f);
          Serial.printf("🔉 Volume diminuído para %.2f\n", volume);
        } 
        else {
          float newVolume = atof(valueStr);
          volume = constrain(newVolume, 0.0f, 1.0f);
          Serial.printf("🔊 Novo volume definido: %.2f\n", volume);
        }
        finishInteraction();
      }
      break;

    case WStype_BIN: {
      if (!receivingAudio) {
        receivingAudio = true;
        Serial.println("[WS] 🔊 Reproduzindo resposta...");
        int16_t silence[256] = {0}; // Buffer de silêncio
        size_t bytesWritten;
        i2s_write(I2S_SPEAKER_PORT, silence, sizeof(silence), &bytesWritten, portMAX_DELAY);
        delay(10); // Pequeno delay para estabilizar o I2S
      }
      uint8_t* audioData = payload;
      size_t audioLength = length;
      if (!headerSkipped && length > 44) {
        audioData += 44;
        audioLength -= 44;
        headerSkipped = true;
      }
      
      bool isEnd = isEndOfAudio(audioData, audioLength);

      if (audioLength > 0) {
        if (volume != 1.0) {
          int16_t* samples = (int16_t*)audioData;
          size_t numSamples = audioLength / sizeof(int16_t);
          adjustVolume(samples, numSamples, volume);
        }
        size_t bytesWritten;
        i2s_write(I2S_SPEAKER_PORT, audioData, audioLength, &bytesWritten, portMAX_DELAY);
      }

      if (isEnd) {
        delay(500);
        Serial.println("[WS] ✅ Interação finalizada");
        finishInteraction();
      }

      break;
    }

    case WStype_DISCONNECTED:
      Serial.println("[WS] ❌ Desconectado");
      clearAudioQueue(); // Limpar fila ao desconectar
      break;

    default:
      break;
  }
}

void finishInteraction() {
  waitingResponse = false;
  recording = false;
  sendingWakeBuffer = false;
  receivingAudio = false;
  headerSkipped = false;
  wakeBufferSending = false;
  clearAudioQueue(); // Limpar fila ao finalizar interação
}

void connectWiFiManager() {
    // read stored server
  String stored = readServerFromPrefs();
  if (stored.length()) websocket_host = stored;
  Serial.println("Server: " + websocket_host);

  WiFiManager wifiManager;

  // Create a custom parameter for server address
  WiFiManagerParameter custom_server("server", "Server URL", websocket_host.c_str(), 128);
  wifiManager.addParameter(&custom_server);

  // Start config portal (blocks until connected)
  if (!wifiManager.autoConnect("ESP32-Config")) {
    Serial.println("Failed to connect and hit timeout");
    // optionally restart
    ESP.restart();
  }
  
  String newServer = custom_server.getValue();
  if (newServer.length() && newServer != websocket_host) {
    websocket_host = newServer;
    saveServerToPrefs(websocket_host);
    Serial.println("Saved new server: " + websocket_host);
  }

}

// ====== SETUP ======
void setup() {
  Serial.begin(115200);
  
  // Inicializar mutex
  audioQueueMutex = xSemaphoreCreateMutex();
  
  setup_i2s_speaker();
  setup_i2s_microphone();
  
  connectWiFiManager();

  webSocket.begin(websocket_host, websocket_port, websocket_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);

  // Criar task de envio de áudio
  xTaskCreatePinnedToCore(
    audioSendTask,        // Função da task
    "AudioSendTask",      // Nome
    4096,                 // Stack size
    NULL,                 // Parâmetros
    1,                    // Prioridade (mais baixa que captura)
    &audioSendTaskHandle, // Handle
    0                     // Core
  );

  Serial.println("🚀 Pronto! Aguardando wake word...");
}

// ====== LOOP ======
void loop() {
  webSocket.loop();
  if (WiFi.status() == WL_CONNECTED && webSocket.isConnected() &&
      !receivingAudio && !waitingResponse) {
    captureAudio();
  }

  // Monitorar status da fila periodicamente
  static unsigned long lastStatusTime = 0;
  if (millis() - lastStatusTime >= 3000) {
    if (xSemaphoreTake(audioQueueMutex, 0) == pdTRUE) {
      int queueSize = audioQueue.size();
      xSemaphoreGive(audioQueueMutex);
      
      //Serial.printf("[QUEUE] Fila: %d/%d | Heap: %d bytes | WakeSending: %d\n", 
      //              queueSize, MAX_QUEUE_SIZE, ESP.getFreeHeap(), wakeBufferSending);
      lastStatusTime = millis();
    }
  }
}

bool shouldSendWakeBuffer(float dynamicThreshold) {
  return (!recording && !waitingResponse && !sendingWakeBuffer && 
          !wakeBufferSending && env > dynamicThreshold);
}

void sendPostWakeAudio(int16_t* s16, size_t samplesRead) {
  // Adicionar à fila em vez de enviar diretamente
  if (addToAudioQueueSmart((uint8_t*)s16, samplesRead * sizeof(int16_t), false)) {
    capturedSamples += samplesRead;
  }

  if (capturedSamples >= (POST_WAKE_SECONDS * SAMPLE_RATE)) {
    // Adicionar marcador de fim à fila
    addToAudioQueueSmart(endMarker, sizeof(endMarker), true);
    sendingWakeBuffer = false;
    Serial.printf("[MIC] 💤 Post-wake finished (%.2fs)\n",
                  (float)capturedSamples / SAMPLE_RATE);
  }
}

void sendContinuousAudio(int16_t* s16, size_t samplesRead, float dynamicSilenceThreshold) {
  // Adicionar à fila em vez de enviar diretamente
  if (addToAudioQueueSmart((uint8_t*)s16, samplesRead * sizeof(int16_t), false)) {
    if (env > dynamicSilenceThreshold) lastSound = millis();
  }

  if (millis() - recordStart > MAX_RECORD_MS ||
      (millis() - lastSound > SILENCE_TIMEOUT_MS)) {
    Serial.println("[MIC] 🛑 Recording ended");
    recording = false;
    waitingResponse = true;

    // Adicionar marcador de fim à fila
    addToAudioQueueSmart(endMarker, sizeof(endMarker), true);
    beepEndRecording();
  }
}

// ===== Métodos auxiliares ========

// ====== BEEP ======
void playBeep(float frequency, int duration_ms) {
  const int amplitude = 3000;
  const float twoPiF = 2 * PI * frequency / SAMPLE_RATE;
  const int bufferSize = 256;
  int16_t samples[bufferSize];

  unsigned long totalSamples = (SAMPLE_RATE * duration_ms) / 1000;
  unsigned long sent = 0;
  while (sent < totalSamples) {
    for (int i = 0; i < bufferSize; i++)
      samples[i] = (int16_t)(amplitude * sin(twoPiF * (sent + i)));
    size_t bytesWritten;
    i2s_write(I2S_SPEAKER_PORT, samples, bufferSize * sizeof(int16_t), &bytesWritten, portMAX_DELAY);
    sent += bufferSize;
  }
  
  delay(duration_ms);
}

void beepReady() { 
  playBeep(1000, 150); 
  delay(100); 
  playBeep(1200, 150);  
}

void beepEndRecording() { 
  playBeep(600, 300); 
}

// ====== BEEP ====== 
float calculateRMS(int32_t *buf, size_t samples) {
  double sumsq = 0.0;

  // Estados do filtro
  static float hp_prev = 0.0;   // Passa-alta
  static float lp_prev = 0.0;   // Passa-baixa

  // Coeficientes do filtro (ajuste conforme taxa de amostragem)
  const float hp_alpha = 0.9f;  // passa-alta (~100 Hz @16 kHz)
  const float lp_alpha = 0.1f;  // passa-baixa (~3 kHz @16 kHz)

  for (size_t i = 0; i < samples; i++) {
    // Normaliza sinal (24-bit -> -1.0 a +1.0)
    int32_t s = buf[i] >> 8;
    float x = (float)s / 32768.0f;

    // --- Passa-alta ---
    float hp = x - hp_prev + hp_alpha * hp_prev;
    hp_prev = hp;

    // --- Passa-baixa ---
    float lp = lp_prev + lp_alpha * (hp - lp_prev);
    lp_prev = lp;

    // Soma quadrados (para RMS)
    sumsq += lp * lp;
  }

  // Calcula RMS final
  return sqrt(sumsq / samples);
}

size_t readMicSamples(int32_t* buffer, size_t bufSize, size_t& bytesRead) {
  i2s_read(I2S_MIC_PORT, buffer, bufSize * sizeof(int32_t), &bytesRead, portMAX_DELAY);
  return bytesRead / sizeof(int32_t);
}

bool isEndOfAudio(uint8_t* data, size_t& length) {
  if (length >= 4 && 
      data[length - 1] == 0xFF &&
      data[length - 2] == 0xFF &&
      data[length - 3] == 0xFF &&
      data[length - 4] == 0xFF) {
    length -= 4;
    return true;
  }
  return false;
}

void updateEnvelopes(float rms) {
  env = alpha * rms + (1.0 - alpha) * env;
  if (!recording && !sendingWakeBuffer && !wakeBufferSending) {
    envNoise = alphaNoise * rms + (1.0 - alphaNoise) * envNoise;
  }
}

void computeThresholds(float& dynamicThreshold, float& dynamicSilenceThreshold) {
  dynamicThreshold = envNoise * 3.0;
  dynamicSilenceThreshold = envNoise * 1.5;
}

void convertAndStoreSamples(int32_t* s32, int16_t* s16, size_t samplesRead) {
  for (size_t i = 0; i < samplesRead; i++) {
    int32_t shifted = s32[i] >> 11;
    s16[i] = (int16_t)constrain(shifted, -32768, 32767);
    wakeBuffer[wakeBufferIndex] = s16[i];
    wakeBufferIndex = (wakeBufferIndex + 1) % wakeBufferSamples;
  }
}

void adjustVolume(int16_t* samples, size_t numSamples, float volume) {
  for (size_t i = 0; i < numSamples; i++) {
    int32_t val = (int32_t)((float)samples[i] * volume);
    if (val > 32767) val = 32767;
    else if (val < -32768) val = -32768;
    samples[i] = (int16_t)val;
  }
}