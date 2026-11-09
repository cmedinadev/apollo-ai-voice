import logging

from openai import AsyncOpenAI

from . import config

log = logging.getLogger("apollo.llm")


class Chat:
    """Per-connection conversation with a bounded history."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client
        self.history: list[dict[str, str]] = []

    def _remember(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        del self.history[: -config.MAX_HISTORY]

    @property
    def last_reply(self) -> str | None:
        if self.history and self.history[-1]["role"] == "assistant":
            return self.history[-1]["content"]
        return None

    async def reply(self, user_text: str) -> str:
        self._remember("user", user_text)
        try:
            resp = await self._client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[{"role": "system", "content": config.SYSTEM_PROMPT}, *self.history],
                timeout=30,
            )
            text = (resp.choices[0].message.content or "").strip()
        except Exception:
            log.exception("OpenAI request failed")
            self.history.pop()  # don't keep an unanswered turn
            return config.MSG_ERROR
        self._remember("assistant", text)
        return text


def make_client() -> AsyncOpenAI:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set (see .env.example)")
    return AsyncOpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)
