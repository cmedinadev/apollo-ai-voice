# 🤖 Apollo AI Voice

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-ESP32%20%7C%20Python-yellow.svg)]()
[![Status](https://img.shields.io/badge/status-ativo-success.svg)]()

[🇬🇧 English](README.md) | [🇧🇷 Português](README.pt_br.md) | [🇪🇸 Español](README.es.md)

**Apollo AI Voice** é um assistente de voz inteligente alimentado por um microcontrolador **ESP32** e um **servidor Python**.  
Ele captura entrada de voz, processa com IA e responde naturalmente através de reprodução de áudio local — criando um dispositivo conversacional totalmente interativo e de baixo custo.

---

## 🧩 Funcionalidades
- 🎙️ Captura de áudio em tempo real usando microfone **INMP441**  
- 🔊 Reprodução local via DAC **MAX98357**  
- 🌐 Comunicação **WebSocket** entre ESP32 e servidor Python  
- 🧠 **Detecção de palavra de ativação** para ativação hands-free  
- 🗣️ **Conversão de Fala em Texto (STT)** usando **OpenAI Whisper**  
- 🤖 Respostas de IA alimentadas por **modelos OpenAI GPT**  
- 🗣️ **Conversão de Texto em Fala (TTS)** natural via **Piper**  
- ⚙️ Arquitetura modular (firmware ESP32 + backend Python)  

---

## 📁 Estrutura do Projeto
```plaintext
apollo-ai-voice/
│
├── esp32/               # ESP32 firmware (C++)
│   ├── src/
│   └── ...
│
├── server/              # Python backend
│   ├── app.py
│   ├── procupine/apollo_wakeword.py
│   ├── procupine/porcupine_params_pt.pv
│   ├── piper_tts.py
│   ├── requirements.txt
│
└── README.md
```

---

## ⚙️ Requisitos

### Para ESP32
- Placa de desenvolvimento ESP32 (ex: ESP32-DevKitC)
- Microfone digital INMP441
- Amplificador I2S MAX98357A
- Arduino IDE ou PlatformIO
- Bibliotecas necessárias:
  - `WiFi.h`
  - `WebSocketsClient.h`
  - `driver/i2s.h`

### Para o Servidor
- Python 3.10+
- Ambiente virtual recomendado (venv)
- Dependências:
  ```bash
  pip install -r requirements.txt
  ```
- As bibliotecas necessárias incluem:
    - websockets
    - numpy
    - scipy
    - whisper
    - openai
    - piper-tts

---

## 🚀 Como Executar

### 1. Gravar o firmware no ESP32
- Abra a pasta `/esp32/` no Arduino IDE ou PlatformIO.
- Configure as credenciais Wi-Fi e o IP do servidor WebSocket.
- Conecte e grave na placa.

### 2. Iniciar o servidor Python

- Navegue até a pasta `/server/`.
- Execute:
```bash
python server.py
```
- O servidor ficará aguardando streams de áudio do ESP32 e processará detecção de palavra de ativação, transcrição e geração de respostas.

### 3. Fluxo de interação

1. O ESP32 aguarda pela palavra de ativação (ex: "Apollo").
2. Ao detectar, transmite o áudio gravado para o servidor.
3. O servidor:
    - Converte fala em texto.
    - Envia o texto para o LLM para processamento.
    - Sintetiza a resposta da IA usando TTS.

4. O ESP32 reproduz a resposta através do alto-falante.

---

## 🧠 Integração com IA (LLM)

O servidor integra com a API da OpenAI (ou LLMs compatíveis) para respostas naturais e contextuais.

Exemplo de código:
```python
import openai

openai.api_key = "SUA_CHAVE_API"

response = openai.ChatCompletion.create(
    model="gpt-4.1-nano",
    messages=[{"role": "user", "content": prompt}]
)

```
Você pode personalizar o prompt do sistema para definir a personalidade, tom ou conhecimento de domínio do Apollo.

---

## 🧠 Como Funciona

1. O ESP32 monitora continuamente a entrada do microfone.
2. Ao detectar a palavra de ativação, começa a transmitir áudio para o servidor Python.
3. O servidor transcreve a fala (Whisper), processa através do OpenAI GPT e gera uma resposta.
4. O motor TTS Piper sintetiza o áudio da resposta.
5. O ESP32 recebe e reproduz a resposta via alto-falante.

---

## 🛡️ Notas de Segurança e Privacidade

- Mantenha suas chaves de API fora do controle de versão (use variáveis de ambiente ou arquivo .env).

- Considere executar os modelos STT/TTS localmente se a privacidade for necessária.

- Valide e sanitize qualquer entrada fornecida pelo usuário antes de enviar para APIs externas.

---

## 📜 Licença

Este projeto está licenciado sob a Licença MIT.

---

## 💬 Autor

Desenvolvido por Cristian Medina

Hardware: ESP32 + INMP441 + MAX98357A

Software: Python, WebSocket, Whisper, Piper e integração com OpenAI GPT.