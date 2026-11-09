import asyncio
import logging
from dataclasses import dataclass

import websockets

from . import config
from .llm import Chat, make_client
from .session import Session
from .stt import Transcriber
from .tts import Synthesizer
from .wakeword import WakeWordDetector

log = logging.getLogger("apollo")


@dataclass
class Services:
    wakeword: WakeWordDetector
    stt: Transcriber
    tts: Synthesizer
    openai: object

    def new_chat(self) -> Chat:
        return Chat(self.openai)


async def serve() -> None:
    log.info("Loading models...")
    services = Services(WakeWordDetector(), Transcriber(), Synthesizer(), make_client())

    async def handler(ws) -> None:
        log.info("ESP32 connected: %s", ws.remote_address)
        try:
            await Session(ws, services).run()
        except websockets.ConnectionClosed:
            pass
        except Exception:
            log.exception("Session error")
        finally:
            log.info("ESP32 disconnected")

    async with websockets.serve(
        handler, config.HOST, config.PORT,
        ping_interval=config.PING_INTERVAL, ping_timeout=config.PING_TIMEOUT,
    ):
        log.info("Listening on ws://%s:%d", config.HOST, config.PORT)
        await asyncio.Future()


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
