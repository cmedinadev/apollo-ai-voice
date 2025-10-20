#include <WiFi.h>
#include <WebSocketsClient.h>
#include "driver/i2s.h"
#include <math.h>

// ====== CONFIG WIFI ======
const char* ssid = "your-network-name";
const char* password = "your-network-password";

// ====== CONFIG WEBSOCKET ======
const char* websocket_host = "XXXXXX";
const int websocket_port = 8080;
const char* websocket_path = "/";
const int SAMPLE_RATE = 16000;
const int PRE_WAKE_SECONDS = 0.5;
const int POST_WAKE_SECONDS = 1.5;
const unsigned long MIN_RECORD_MS = 300;
const int  QAKE_WORD = 1000;

WebSocketsClient webSocket;

// ====== CONFIG I2S ======
#define I2S_MIC_PORT I2S_NUM_0
#define I2S_MIC_WS   33
#define I2S_MIC_SD   32
#define I2S_MIC_SCK  14

#define I2S_SPEAKER_PORT I2S_NUM_1
#define I2S_SPEAKER_DOUT 22 
#define I2S_SPEAKER_BCLK 19
#define I2S_SPEAKER_LRC  21

// ====== ESTADOS ======
bool sendingWakeBuffer = false;
bool recording = false;
bool waitingResponse = false;
bool receivingAudio = false;
bool headerSkipped = false;

const unsigned long MAX_RECORD_MS = 15000;
const unsigned long SILENCE_TIMEOUT_MS = 1500;
unsigned long recordStart = 0;
unsigned long lastSound = 0;
unsigned long postWakeStartTime = 0;

float wakeThreshold = 0.014;
float wakeThresholdSilence = 0.01;

// ====== BUFFER DE WAKE WORD (1s de áudio) ======
const int wakeBufferSamples = SAMPLE_RATE;
int16_t wakeBuffer[wakeBufferSamples];
int wakeBufferIndex = 0;

// ====== PROTÓTIPOS ======
void setup_i2s_microphone();
void setup_i2s_speaker();
void captureAudio();
void connectWiFi();
void playBeep(float frequency, int duration_ms);
void beepReady();
void beepEndRecording();

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
      .use_apll = false
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

// ====== RMS ======
float calculateRMS(int32_t *samples, size_t count) {
  double sum = 0;
  for (size_t i = 0; i < count; i++) {
    int32_t raw = samples[i] >> 8;
    float s = raw / 8388607.0f;
    sum += s * s;
  }
  return sqrt(sum / count);
}

// ====== CAPTURA ======
void captureAudio() {
  const size_t bufSize = 512;
  int32_t s32[bufSize];
  int16_t s16[bufSize];
  size_t bytesRead = 0;

  i2s_read(I2S_MIC_PORT, s32, bufSize * sizeof(int32_t), &bytesRead, portMAX_DELAY);
  size_t samplesRead = bytesRead / sizeof(int32_t);

  for (size_t i = 0; i < samplesRead; i++) {
    int32_t shifted = s32[i] >> 11;
    s16[i] = (int16_t)constrain(shifted, -32768, 32767);
    // salva no buffer circular
    wakeBuffer[wakeBufferIndex] = s16[i];
    wakeBufferIndex = (wakeBufferIndex + 1) % wakeBufferSamples;
  }

  float rms = calculateRMS(s32, samplesRead);

  // ====== ENVIO DE BUFFER DE WAKE WORD ======
  if (!recording && !waitingResponse && !sendingWakeBuffer && rms > wakeThreshold) {
      Serial.println("[MIC] 🚀 Enviando buffer de wake word...");
      sendingWakeBuffer = true;
      webSocket.sendTXT("wake_buffer_start");
      postWakeStartTime = millis();
      // Envia 1s de áudio armazenado
      int startIdx = (wakeBufferIndex + 1) % wakeBufferSamples;
      for (int i = 0; i < wakeBufferSamples; i += bufSize) {
        int idx = (startIdx + i) % wakeBufferSamples;
        size_t chunk = min(bufSize, (size_t)(wakeBufferSamples - i));
        webSocket.sendBIN((uint8_t*)&wakeBuffer[idx], chunk * sizeof(int16_t));
      }
  }

  if (sendingWakeBuffer && postWakeStartTime > 0) {
    // envia POST_WAKE_SECONDS de áudio depois do buffer
    webSocket.sendBIN((uint8_t*)s16, samplesRead * sizeof(int16_t));
    if (millis() - postWakeStartTime >= (POST_WAKE_SECONDS * 1000)) {
      postWakeStartTime = 0;
      webSocket.sendTXT("wake_buffer_end");
      Serial.println("[MIC] 💤 Aguardando confirmação do servidor...");
    }
  }

  // ====== ENVIO DE ÁUDIO CONTÍNUO ======
  if (recording) {
    webSocket.sendBIN((uint8_t*)s16, samplesRead * sizeof(int16_t));
    if (rms > wakeThresholdSilence) lastSound = millis();

    if (millis() - recordStart > MAX_RECORD_MS ||
        (millis() - lastSound > SILENCE_TIMEOUT_MS)) {
      Serial.println("[MIC] 🛑 Fim da gravação");
      recording = false;
      waitingResponse = true;
      webSocket.sendTXT("end_audio");
      beepEndRecording();
    }
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
        sendingWakeBuffer = false;
        recording = true;
        recordStart = millis();
        lastSound = millis();
        beepReady();
        webSocket.sendTXT("start_audio");
      } 
      else if (strcmp((char*)payload, "wake_word_rejected") == 0) {
        Serial.println("[WS] 🎤 Wake word rejeitada!");
        sendingWakeBuffer = false;
        recording = false;
      } 
      else if (strcmp((char*)payload, "interaction_ended") == 0) {
        waitingResponse = false;
        recording = false;
        sendingWakeBuffer = false;
        receivingAudio = false;
        Serial.println("[WS] ✅ Interação finalizada");
      }

      break;

    case WStype_BIN: {
      if (!receivingAudio) {
        receivingAudio = true;
        Serial.println("[WS] 🔊 Reproduzindo resposta...");
      }
      uint8_t* audioData = payload;
      size_t audioLength = length;
      if (!headerSkipped && length > 44) {
        audioData += 44;
        audioLength -= 44;
        headerSkipped = true;
      }
      size_t bytesWritten;
      i2s_write(I2S_SPEAKER_PORT, audioData, audioLength, &bytesWritten, portMAX_DELAY);
      break;
    }

    case WStype_DISCONNECTED:
      Serial.println("[WS] ❌ Desconectado");
      break;

    default:
      break;
  }
}

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
}

void beepReady() { playBeep(1000, 150); delay(100); playBeep(1200, 150); }
void beepEndRecording() { playBeep(600, 300); }

// ====== WI-FI ======
void connectWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Conectando");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\n✅ Wi-Fi conectado");
  Serial.println(WiFi.localIP());
}

// ====== SETUP ======
void setup() {
  Serial.begin(115200);
  setup_i2s_speaker();
  setup_i2s_microphone();
  connectWiFi();

  webSocket.begin(websocket_host, websocket_port, websocket_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);

  Serial.println("🚀 Pronto! Aguardando wake word...");
}

// ====== LOOP ======
void loop() {
  webSocket.loop();
  if (WiFi.status() == WL_CONNECTED && webSocket.isConnected() &&
      !receivingAudio && !waitingResponse) {
    captureAudio();
  }
}