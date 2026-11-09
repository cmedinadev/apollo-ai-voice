"""WAV / PCM helpers and optional noise cleanup."""

import io
import logging
import wave

import numpy as np

from . import config

log = logging.getLogger("apollo.audio")


def pcm16_to_float32(pcm: bytes) -> np.ndarray:
    usable = len(pcm) - (len(pcm) % 2)
    return np.frombuffer(pcm[:usable], dtype=np.int16).astype(np.float32) / 32768.0


def pcm16_to_wav(pcm: bytes, sample_rate: int = config.SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def save_debug(name: str, pcm: bytes) -> None:
    """Dump received audio to disk when DEBUG_SAVE_AUDIO=1."""
    if config.DEBUG_AUDIO_DIR is None:
        return
    config.DEBUG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    (config.DEBUG_AUDIO_DIR / name).write_bytes(pcm16_to_wav(pcm))


def clean(audio: np.ndarray, sr: int = config.SAMPLE_RATE) -> np.ndarray:
    """Band-pass 100-7000 Hz, spectral noise reduction, peak normalise."""
    from scipy.signal import butter, filtfilt
    import noisereduce as nr

    nyq = sr / 2
    b, a = butter(4, [100 / nyq, 7000 / nyq], btype="band")
    out = filtfilt(b, a, audio)
    out = nr.reduce_noise(y=out, sr=sr, y_noise=out[: int(sr * 0.5)], prop_decrease=0.9)
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    return (out / peak * 0.95).astype(np.float32) if peak > 0 else out.astype(np.float32)
