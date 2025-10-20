# 🤖 Apollo AI Voice

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-ESP32%20%7C%20Python-yellow.svg)]()
[![Status](https://img.shields.io/badge/status-activo-success.svg)]()

[🇬🇧 English](README.md) | [🇧🇷 Português](README.pt_br.md) | [🇪🇸 Español](README.es.md)

**Apollo AI Voice** es un asistente de voz inteligente impulsado por un microcontrolador **ESP32** y un **servidor Python**.  
Captura entrada de voz, la procesa con IA y responde naturalmente a través de reproducción de audio local — creando un dispositivo conversacional totalmente interactivo y de bajo costo.

---

## 🧩 Características
- 🎙️ Captura de audio en tiempo real usando micrófono **INMP441**  
- 🔊 Reproducción local vía DAC **MAX98357**  
- 🌐 Comunicación **WebSocket** entre ESP32 y servidor Python  
- 🧠 **Detección de palabra de activación** para activación manos libres  
- 🗣️ **Conversión de Voz a Texto (STT)** usando **OpenAI Whisper**  
- 🤖 Respuestas de IA impulsadas por **modelos OpenAI GPT**  
- 🗣️ **Conversión de Texto a Voz (TTS)** natural vía **Piper**  
- ⚙️ Arquitectura modular (firmware ESP32 + backend Python)  

---

## 📁 Estructura del Proyecto
```plaintext
apollo-ai-voice/
│
├── esp32/               # ESP32 firmware (C++)
│   ├── src/
│   └── ...
│
├── server/              # Python backend
│   ├── porcupine/apollo_wakeword.py
│   ├── porcupine/porcupine_params_pt.pv
│   ├── server.py
│   ├── piper_tts.py
│   ├── requirements.txt
│
└── README.md
```

---

## ⚙️ Requisitos

### Para ESP32
- Placa de desarrollo ESP32 (ej: ESP32-DevKitC)
- Micrófono digital INMP441
- Amplificador I2S MAX98357A
- Arduino IDE o PlatformIO
- Bibliotecas requeridas:
  - `WiFi.h`
  - `WebSocketsClient.h`
  - `driver/i2s.h`

### Para el Servidor
- Python 3.10+
- Entorno virtual recomendado (venv)
- Dependencias:
  ```bash
  pip install -r requirements.txt
  ```
- Las bibliotecas requeridas incluyen:
    - websockets
    - numpy
    - scipy
    - whisper
    - openai
    - piper-tts

---

## 🚀 Cómo Ejecutar

### 1. Flashear el firmware del ESP32
- Abre la carpeta `/esp32/` en Arduino IDE o PlatformIO.
- Configura las credenciales Wi-Fi y la IP del servidor WebSocket.
- Conecta y flashea la placa.

### 2. Iniciar el servidor Python

- Navega hasta la carpeta `/server/`.
- Ejecuta:
```bash
python server.py
```
- El servidor esperará streams de audio del ESP32 y manejará la detección de palabra de activación, transcripción y generación de respuestas.

### 3. Flujo de interacción

1. El ESP32 espera por la palabra de activación (ej: "Apollo").
2. Al detectarla, transmite el audio grabado al servidor.
3. El servidor:
    - Convierte la voz en texto.
    - Envía el texto al LLM para procesamiento.
    - Sintetiza la respuesta de la IA usando TTS.

4. El ESP32 reproduce la respuesta a través del altavoz.

---

## 🧠 Integración con IA (LLM)

El servidor se integra con la API de OpenAI (o LLMs compatibles) para respuestas naturales y contextuales.

Ejemplo de código:
```python
import openai

openai.api_key = "TU_CLAVE_API"

response = openai.ChatCompletion.create(
    model="gpt-4.1-nano",
    messages=[{"role": "user", "content": prompt}]
)

```
Puedes personalizar el prompt del sistema para definir la personalidad, tono o conocimiento de dominio de Apollo.

---

## 🧠 Cómo Funciona

1. El ESP32 monitorea continuamente la entrada del micrófono.
2. Al detectar la palabra de activación, comienza a transmitir audio al servidor Python.
3. El servidor transcribe el habla (Whisper), la procesa a través de OpenAI GPT y genera una respuesta.
4. El motor TTS Piper sintetiza el audio de la respuesta.
5. El ESP32 recibe y reproduce la respuesta vía altavoz.

---

## 🛡️ Notas de Seguridad y Privacidad

- Mantén tus claves API fuera del control de versiones (usa variables de entorno o un archivo .env).

- Considera ejecutar los modelos STT/TTS localmente si la privacidad es necesaria.

- Valida y sanitiza cualquier entrada proporcionada por el usuario antes de enviarla a APIs externas.

---

## 📜 Licencia

Este proyecto está licenciado bajo la Licencia MIT.

---

## 💬 Autor

Desarrollado por Cristian Medina

Hardware: ESP32 + INMP441 + MAX98357A

Software: Python, WebSocket, Whisper, Piper e integración con OpenAI GPT.