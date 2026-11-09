import asyncio
import logging

import whisper

from . import audio, config

log = logging.getLogger("apollo.stt")


class Transcriber:
    def __init__(self) -> None:
        log.info("Loading Whisper '%s'...", config.WHISPER_MODEL)
        self._model = whisper.load_model(config.WHISPER_MODEL)

    async def transcribe(self, pcm: bytes) -> str:
        samples = audio.pcm16_to_float32(pcm)
        if samples.size == 0:
            return ""
        if config.CLEAN_AUDIO:
            samples = await asyncio.to_thread(audio.clean, samples)
        result = await asyncio.to_thread(
            self._model.transcribe, samples, fp16=False, language=config.WHISPER_LANGUAGE
        )
        return result["text"].strip()
