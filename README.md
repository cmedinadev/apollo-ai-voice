# 🤖 Apollo AI Voice

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-ESP32%20%7C%20Python-yellow.svg)]()
[![Status](https://img.shields.io/badge/status-active-success.svg)]()


[🇬🇧 English](README.md) | [🇧🇷 Português](README.pt_br.md) | [🇪🇸 Español](README.es.md)

**Apollo AI Voice** is an intelligent voice assistant powered by an **ESP32** microcontroller and a **Python server**.  
It captures voice input, processes it with AI, and responds naturally through local audio playback — creating a fully interactive and low-cost conversational device.

---

## 🧩 Features
- 🎙️ Real-time audio capture using **INMP441** microphone  
- 🔊 Local playback via **MAX98357** DAC  
- 🌐 **WebSocket** communication between ESP32 and Python server  
- 🧠 **Wake word detection** for hands-free activation  
- 🗣️ **Speech-to-Text (STT)** using **OpenAI Whisper**  
- 🤖 AI responses powered by **OpenAI GPT models**  
- 🗣️ Natural **Text-to-Speech (TTS)** via **Piper**  
- ⚙️ Modular architecture (ESP32 firmware + Python backend)  

---

## 📁 Project Structure
```plaintext
apollo-ai-voice/
│
├── esp32/               # ESP32 firmware (C++)
│   ├── src/
│   └── ...
│
├── server/              # Python backend
│   ├── apollo/          # config, session (protocol), stt, llm, tts, wakeword
│   ├── porcupine/       # .ppn keyword + .pv model (Porcupine 4.x)
│   ├── tests/
|
├── piper/               # Piper TTS Binary and Models
│   ├── /models
│   ├── /models/pt_BR-faber-medium.onnx
│   ├── /models/pt_BR-faber-medium.onnx.json
│
└── README.md
````

---

## ⚙️ Requirements

### For ESP32
- ESP32 development board (e.g., ESP32-DevKitC)
- INMP441 digital microphone
- MAX98357A I2S amplifier
- Arduino IDE or PlatformIO
- Required libraries:
  - `WiFi.h`
  - `WebSocketsClient.h`
  - `driver/i2s.h`

### For Server
- Python 3.10+
- Recommended virtual environment (venv)
- Dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- Required libraries include:
    - websockets
    - numpy
    - scipy
    - whisper
    - openai

---

## 🔊 Install Audio Tools

Piper TTS (Binary)

Download the latest release of Piper (text-to-speech engine):

Linux
```bash
curl -L -o piper.tar.gz https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz
tar -xzf piper_linux_x86_64.tar.gz
cd piper
chmod +x piper
````

MacOS
```bash
# Para Intel (x86_64)
curl -L -O https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_macos_x86_64.tar.gz
   
# Para Apple Silicon (ARM64)
curl -L -O https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_macos_aarch64.tar.gz
tar -xzf piper_macos_aarch64.tar.gz
cd piper
chmod +x piper
```

Windows PowerShell
```powershell
Invoke-WebRequest -Uri https://github.com/rhasspy/piper/releases/latest/download/piper_windows_amd64.zip -OutFile piper.zip
Expand-Archive -Path piper.zip -DestinationPath .
```

Download a Portuguese voice model:

```bash
mkdir models
cd models
curl -L -o pt_BR-faber-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx
curl -L -o pt_BR-faber-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json
```

---

Sox (Audio Player)

Used to play generated audio locally.

Linux
```bash
sudo apt install sox
```

MacOs
```bash
brew install sox
```

Windows

Download from https://sourceforge.net/projects/sox/
and add it to your system PATH.

---

## 🚀 How to Run

### 1. Flash the ESP32 firmware
- Open the /esp32/ folder in Arduino IDE or PlatformIO.
- Configure Wi-Fi credentials and WebSocket server IP.
- Connect and flash the board.

### 2. Start the Python server

- Create a venv and install deps: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Copy `.env.example` to `.env` and set `OPENAI_API_KEY` and `PICOVOICE_ACCESS_KEY`.
- Run from the `server/` folder:
```bash
../.venv/bin/python -m apollo
```
- Tests (simulated ESP32): `../.venv/bin/python tests/test_protocol.py`
- The server will listen for incoming audio streams from the ESP32 and handle wake word detection, transcription, and response generation.

### 3. Interaction flow

1. ESP32 waits for the wake word (e.g., “Apollo”).
2. Upon detection, it streams recorded audio to the server.
3. The server:
    - Converts speech to text.
    - Sends text to the LLM for processing.
    - Synthesizes the AI response using TTS.

4. ESP32 plays the response through the speaker.


---


## 🧠 AI Integration (LLM)

The server integrates with OpenAI’s API (or compatible LLMs) for natural, contextual responses.

Example snippet:
```python
import openai

openai.api_key = "YOUR_API_KEY"

response = openai.ChatCompletion.create(
    model="gpt-4.1-nano",
    messages=[{"role": "user", "content": prompt}]
)

```
You can customize the system prompt to define Apollo’s personality, tone, or domain knowledge.

---

## 🧠 How It Works

1. ESP32 continuously monitors microphone input.
2. On wake word detection, it starts streaming audio to the Python server.
3. The server transcribes the speech (Whisper), processes it through OpenAI GPT, and generates a response.
4. The Piper TTS engine synthesizes the response audio.
5. The ESP32 receives and plays the response via speaker.

---

## 🛡️ Security & Privacy Notes

- Keep your API keys out of source control (use environment variables or a .env file).

- Consider running STT/TTS models locally if privacy is required.

- Validate and sanitize any user-provided input before sending to external APIs.

---

## 📜 License

This project is licensed under the MIT License.

---

## 💬 Author

Developed by Cristian Medina

Hardware: ESP32 + INMP441 + MAX98357A

Software: Python, WebSocket, Whisper, Piper, and OpenAI GPT integration.