"""Piper TTS -> 16 kHz mono WAV (what the ESP32 plays), optional pitch shift."""

import asyncio
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import config

log = logging.getLogger("apollo.tts")


class Synthesizer:
    def __init__(self) -> None:
        if not config.PIPER_MODEL.exists():
            raise FileNotFoundError(f"Piper model not found: {config.PIPER_MODEL}")
        self._sox = shutil.which("sox")
        self._ffmpeg = shutil.which("ffmpeg")
        if not (self._sox or self._ffmpeg):
            raise RuntimeError("Need sox or ffmpeg installed (brew install sox ffmpeg)")
        if config.TTS_PITCH_SEMITONES and not self._sox:
            log.warning("sox not found: pitch shift disabled")

    async def synthesize(self, text: str) -> bytes:
        return await asyncio.to_thread(self._synthesize, text)

    def _synthesize(self, text: str) -> bytes:
        with tempfile.TemporaryDirectory(prefix="apollo_tts_") as tmp:
            raw, out = Path(tmp, "raw.wav"), Path(tmp, "out.wav")
            subprocess.run(
                [
                    sys.executable, "-m", "piper",
                    "--model", str(config.PIPER_MODEL),
                    "--length-scale", str(config.TTS_LENGTH_SCALE),
                    "--noise-scale", str(config.TTS_NOISE_SCALE),
                    "--noise-w-scale", str(config.TTS_NOISE_W),
                    "--output-file", str(raw),
                ],
                input=text, text=True, check=True, capture_output=True, timeout=config.TTS_TIMEOUT,
            )
            if self._sox:
                cmd = ["sox", str(raw), "-r", str(config.SAMPLE_RATE), "-c", "1", str(out)]
                if config.TTS_PITCH_SEMITONES:
                    cmd += ["pitch", str(config.TTS_PITCH_SEMITONES * 100)]
            else:
                cmd = ["ffmpeg", "-y", "-i", str(raw), "-ar", str(config.SAMPLE_RATE), "-ac", "1", str(out)]
            subprocess.run(cmd, check=True, capture_output=True, timeout=config.TTS_TIMEOUT)
            return out.read_bytes()
