"""Wake word via Whisper: synthesised speech with / without the wake word."""

import asyncio
import io
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apollo import config
from apollo.tts import Synthesizer
from apollo.stt import Transcriber
from apollo.wakeword import WakeWordDetector, matches


def test_fuzzy_matching():
    w, t = config.WAKE_WORDS, config.WAKE_MATCH_THRESHOLD
    for ok in ["Apolo", "Apollo, tudo bem?", "a polo", "Ei Apoló!"]:
        assert matches(ok, w, t), ok
    for bad in ["", "Bom dia, tudo bem?", "Obrigado.", "Que horas são?"]:
        assert not matches(bad, w, t), bad


def _pcm(text):
    wav = asyncio.run(Synthesizer().synthesize(text))
    with wave.open(io.BytesIO(wav)) as w:
        return w.readframes(w.getnframes())


def test_detector_on_speech():
    d = WakeWordDetector(Transcriber())
    assert d.detect(_pcm("Apolo"))
    assert d.detect(_pcm("Apolo, que horas são?"))
    assert not d.detect(_pcm("Bom dia, como vai você hoje?"))
    assert not d.detect(b"\x00\x00" * 16000)


if __name__ == "__main__":
    test_fuzzy_matching(); test_detector_on_speech(); print("ok")
