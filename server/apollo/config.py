"""Central configuration. Secrets come from environment variables / .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SERVER_DIR.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(SERVER_DIR / ".env")


def _path(value: str) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else (SERVER_DIR / p).resolve()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- Network ---
HOST = os.getenv("APOLLO_HOST", "0.0.0.0")
PORT = int(os.getenv("APOLLO_PORT", "1969"))
PING_INTERVAL = 20
PING_TIMEOUT = 60

# --- Audio (must match esp32/src/apollo_client.ino) ---
SAMPLE_RATE = 16000
SEND_CHUNK_BYTES = 1024
END_MARKER = b"\xff\xff\xff\xff"
MAX_RECORD_BYTES = SAMPLE_RATE * 2 * 30  # safety cap: 30 s of 16-bit mono

# --- Wake word (Picovoice Porcupine) ---
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "")
WAKEWORD_PATH = _path(os.getenv("WAKEWORD_PATH", "porcupine/apolo_pt_mac_v4_0_0.ppn"))
PORCUPINE_MODEL_PATH = _path(os.getenv("PORCUPINE_MODEL_PATH", "porcupine/porcupine_params_pt.pv"))

# --- STT (Whisper) ---
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "pt")
CLEAN_AUDIO = _bool("CLEAN_AUDIO", False)

# --- LLM (OpenAI) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")
MAX_HISTORY = 6
SYSTEM_PROMPT = os.getenv(
    "APOLLO_SYSTEM_PROMPT",
    "Você é Apollo, um astronauta inteligente e sua missão é conversar e brincar com crianças.\n"
    "Responda em português com frases curtas, de forma alegre e carinhosa.\n"
    "Evite temas adultos, palavrões ou assuntos sérios.\n"
    "Conte histórias, curiosidades e piadas engraçadas.\n"
    "Sugira brincadeiras de adivinhas e outras.\n"
    "Se receber uma mensagem indecifrável ou sem sentido, responda educadamente que não entendeu.\n"
    "Nunca responda com emojis.",
)
MSG_ERROR = "Desculpe, perdi contato com a Terra. Tente novamente."
MSG_NOTHING_TO_REPEAT = "Desculpe, não há nada para repetir."

# --- TTS (Piper) ---
PIPER_MODEL = _path(os.getenv("PIPER_MODEL", "../piper/models/pt_BR-faber-medium.onnx"))
TTS_PITCH_SEMITONES = int(os.getenv("TTS_PITCH_SEMITONES", "2"))
TTS_LENGTH_SCALE = float(os.getenv("TTS_LENGTH_SCALE", "1.0"))
TTS_NOISE_SCALE = 0.667
TTS_NOISE_W = 0.8
TTS_TIMEOUT = 30

# --- Debug ---
DEBUG_AUDIO_DIR = _path(os.getenv("DEBUG_AUDIO_DIR", "debug_audio")) if _bool("DEBUG_SAVE_AUDIO", False) else None
