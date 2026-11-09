"""Wake word detection by transcribing the ESP32's wake buffer with a small Whisper model.

The ESP32 only sends a buffer when it hears sound, so this runs on demand,
not continuously. Matching is fuzzy because Whisper may write "Apolo",
"Apollo", "a polo", "Apoló"...
"""

import difflib
import logging
import re
import unicodedata

import numpy as np

from . import audio, config

log = logging.getLogger("apollo.wakeword")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^a-z ]", " ", text.encode("ascii", "ignore").decode())


def matches(text: str, words: list[str], threshold: float) -> bool:
    tokens = _norm(text).split()
    if not tokens:
        return False
    joined = "".join(tokens)
    for word in words:
        word = _norm(word).strip()
        if word in joined:  # also catches "a polo" -> "apolo"
            return True
        if any(difflib.SequenceMatcher(None, t, word).ratio() >= threshold for t in tokens):
            return True
    return False


class WakeWordDetector:
    def __init__(self, transcriber) -> None:
        self._stt = transcriber

    def detect(self, pcm: bytes) -> bool:
        """True if the wake word is heard in 16 kHz int16 mono PCM. Blocking: run in a thread."""
        samples = audio.pcm16_to_float32(pcm)
        if samples.size == 0 or float(np.sqrt(np.mean(samples**2))) < config.WAKE_MIN_RMS:
            return False
        text = self._stt.transcribe_samples(
            samples, condition_on_previous_text=False, temperature=(0.0, 0.2),
            compression_ratio_threshold=2.0, sample_len=24,
        )
        hit = matches(text, config.WAKE_WORDS, config.WAKE_MATCH_THRESHOLD)
        log.info("Wake buffer heard: %r -> %s", text, "MATCH" if hit else "no match")
        return hit
