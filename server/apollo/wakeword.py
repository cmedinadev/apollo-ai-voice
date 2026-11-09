import logging

import numpy as np
import pvporcupine

from . import config

log = logging.getLogger("apollo.wakeword")


class WakeWordDetector:
    def __init__(self) -> None:
        if not config.PICOVOICE_ACCESS_KEY:
            raise RuntimeError("PICOVOICE_ACCESS_KEY not set (see .env.example)")
        self._porcupine = pvporcupine.create(
            access_key=config.PICOVOICE_ACCESS_KEY,
            keyword_paths=[str(config.WAKEWORD_PATH)],
            model_path=str(config.PORCUPINE_MODEL_PATH),
        )
        self._frame_bytes = self._porcupine.frame_length * 2

    def detect(self, pcm: bytes) -> bool:
        """True if the wake word occurs anywhere in 16 kHz int16 mono PCM."""
        self._porcupine.reset()
        for i in range(0, len(pcm) - self._frame_bytes + 1, self._frame_bytes):
            frame = np.frombuffer(pcm[i : i + self._frame_bytes], dtype=np.int16)
            if self._porcupine.process(frame) >= 0:
                return True
        return False
