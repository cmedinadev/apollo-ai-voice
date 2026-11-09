"""Spoken commands handled locally instead of going to the LLM."""

import re
import unicodedata

_LEVELS = {
    "um": 0.1, "dois": 0.2, "tres": 0.3, "quatro": 0.4, "cinco": 0.5,
    "seis": 0.6, "sete": 0.7, "oito": 0.8, "nove": 0.9, "dez": 1.0,
    "maximo": 1.0, "baixo": 0.2, "medio": 0.5, "alto": 0.8,
}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.strip().lower())
    return re.sub(r"[^a-z0-9 .]", "", text.encode("ascii", "ignore").decode())


def parse_volume(text: str) -> str | None:
    """Return the 'set_volume:<x>' message for the ESP32, or None."""
    t = _norm(text)
    if t.startswith(("aumente", "aumenta")):
        return "set_volume:+"
    if t.startswith(("diminua", "diminui", "abaixe", "abaixa")):
        return "set_volume:-"
    if not t.startswith(("volume", "colume")):
        return None
    m = re.search(r"\d+(\.\d+)?", t)
    if m:
        return f"set_volume:{min(max(float(m.group()) / 10, 0.0), 1.0):.1f}"
    for word, value in _LEVELS.items():
        if re.search(rf"\b{word}\b", t):
            return f"set_volume:{value:.1f}"
    return None


def is_repeat(text: str) -> bool:
    return _norm(text).rstrip(". ") in ("repita", "repete", "repetir")
