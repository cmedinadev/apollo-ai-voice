import asyncio
import logging
import threading

import numpy as np
import whisper

from . import audio, config

log = logging.getLogger("apollo.stt")


class Transcriber:
    """Single Whisper model shared by wake-word detection and speech recognition."""

    def __init__(self) -> None:
        log.info("Loading Whisper '%s'...", config.WHISPER_MODEL)
        self._model = whisper.load_model(config.WHISPER_MODEL)
        self._lock = threading.Lock()

    def transcribe_samples(self, samples: np.ndarray, **options) -> str:
        """Blocking; run in a thread. Expects 16 kHz float32 mono."""
        with self._lock:
            result = self._model.transcribe(
                audio.normalize(samples), fp16=False, language=config.WHISPER_LANGUAGE, **options
            )
        return result["text"].strip()

    async def transcribe(self, pcm: bytes) -> str:
        samples = audio.pcm16_to_float32(pcm)
        if samples.size == 0:
            return ""
        if config.CLEAN_AUDIO:
            samples = await asyncio.to_thread(audio.clean, samples)
        return await asyncio.to_thread(self.transcribe_samples, samples)
