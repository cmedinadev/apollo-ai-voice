"""End-to-end protocol test: simulated ESP32 <-> real Session with fake wake word / LLM.

Run from server/:  python -m pytest tests -q   (or: python tests/test_protocol.py)
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import websockets

from apollo import config
from apollo.llm import Chat
from apollo.session import Session
from apollo.tts import Synthesizer


class FakeWake:
    def detect(self, pcm):
        return len(pcm) > 0


class FakeSTT:
    def __init__(self, text):
        self.text = text

    async def transcribe(self, pcm):
        return self.text


class FakeCompletions:
    async def create(self, **kw):
        msg = SimpleNamespace(content="Olá, astronauta!")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


FAKE_OPENAI = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))


async def _converse(spoken: str):
    svc = SimpleNamespace(
        wakeword=FakeWake(), stt=FakeSTT(spoken), tts=Synthesizer(), new_chat=lambda: Chat(FAKE_OPENAI)
    )

    async def handler(ws):
        await Session(ws, svc).run()

    async with websockets.serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            pcm = b"\x01\x00" * 16000
            await ws.send("wake_buffer_start")
            await ws.send(pcm)
            await ws.send(config.END_MARKER)
            assert await ws.recv() == "wake_word_detected"

            await ws.send("start_audio")
            await ws.send(pcm)
            await ws.send(config.END_MARKER)
            got = []
            while True:
                m = await asyncio.wait_for(ws.recv(), 30)
                got.append(m)
                if isinstance(m, str) or m == config.END_MARKER:
                    return got


def test_chat_reply_streams_wav():
    got = asyncio.run(_converse("Oi Apollo"))
    assert got[0][:4] == b"RIFF" and got[-1] == config.END_MARKER


def test_volume_command():
    assert asyncio.run(_converse("Volume cinco")) == ["set_volume:0.5"]


def test_no_speech_ends_interaction():
    assert asyncio.run(_converse("")) == ["interaction_ended"]


if __name__ == "__main__":
    test_chat_reply_streams_wav(); test_volume_command(); test_no_speech_ends_interaction()
    print("ok")
