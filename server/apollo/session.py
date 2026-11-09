"""One WebSocket connection = one ESP32 session.

Protocol (see esp32/src/apollo_client.ino):
  ESP32 -> "wake_buffer_start", PCM chunks..., END_MARKER   (wake word candidate)
  server -> "wake_word_detected" | "wake_word_rejected"
  ESP32 -> "start_audio", PCM chunks..., END_MARKER         (user utterance)
  server -> "set_volume:<x>" | "interaction_ended" | WAV chunks..., END_MARKER
"""

import asyncio
import enum
import logging

from . import audio, commands, config

log = logging.getLogger("apollo.session")


class Mode(enum.Enum):
    IDLE = "idle"
    WAKE = "wake"
    RECORD = "record"


class Session:
    def __init__(self, ws, services) -> None:
        self.ws = ws
        self.svc = services  # .wakeword .stt .tts .new_chat()
        self.chat = services.new_chat()
        self.mode = Mode.IDLE
        self.buf = bytearray()

    async def run(self) -> None:
        async for message in self.ws:
            if isinstance(message, str):
                await self._on_text(message)
            else:
                await self._on_binary(bytes(message))

    # ---- incoming ----

    async def _on_text(self, msg: str) -> None:
        if msg == "ping":
            await self.ws.send("pong")
        elif msg == "wake_buffer_start":
            self.mode, self.buf = Mode.WAKE, bytearray()
        elif msg == "start_audio":
            self.mode, self.buf = Mode.RECORD, bytearray()
        else:
            log.info("Unknown text message: %r", msg)

    async def _on_binary(self, data: bytes) -> None:
        if data == config.END_MARKER:
            mode, pcm = self.mode, bytes(self.buf)
            self.mode, self.buf = Mode.IDLE, bytearray()
            if mode is Mode.WAKE:
                await self._finish_wake(pcm)
            elif mode is Mode.RECORD:
                await self._finish_record(pcm)
            return
        if self.mode is not Mode.IDLE and len(self.buf) < config.MAX_RECORD_BYTES:
            self.buf.extend(data)

    # ---- stages ----

    async def _finish_wake(self, pcm: bytes) -> None:
        audio.save_debug("wake.wav", pcm)
        hit = await asyncio.to_thread(self.svc.wakeword.detect, pcm)
        log.info("Wake word %s (%d bytes)", "DETECTED" if hit else "rejected", len(pcm))
        await self.ws.send("wake_word_detected" if hit else "wake_word_rejected")

    async def _finish_record(self, pcm: bytes) -> None:
        audio.save_debug("input.wav", pcm)
        try:
            await self._respond(pcm)
        except Exception:
            log.exception("Pipeline failed")
            await self.ws.send("interaction_ended")

    async def _respond(self, pcm: bytes) -> None:
        text = await self.svc.stt.transcribe(pcm)
        if not text:
            log.info("No speech detected")
            await self.ws.send("interaction_ended")
            return
        log.info("User: %s", text)

        volume = commands.parse_volume(text)
        if volume:
            log.info("Volume command -> %s", volume)
            await self.ws.send(volume)
            return

        if commands.is_repeat(text):
            reply = self.chat.last_reply or config.MSG_NOTHING_TO_REPEAT
        else:
            reply = await self.chat.reply(text)
        log.info("Apollo: %s", reply)

        wav = await self.svc.tts.synthesize(reply)
        await self._send_audio(wav)

    async def _send_audio(self, wav: bytes) -> None:
        """Stream paced slightly faster than real time so the ESP32 never starves or overflows."""
        n = config.SEND_CHUNK_BYTES
        for i in range(0, len(wav), n):
            chunk = wav[i : i + n]
            await self.ws.send(chunk)
            await asyncio.sleep(len(chunk) / 2 / config.SAMPLE_RATE * 0.8)
        await self.ws.send(config.END_MARKER)
