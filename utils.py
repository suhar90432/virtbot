"""Форматирование денег и количеств."""
from __future__ import annotations


def money(kopecks: int) -> str:
    rub = kopecks / 100
    if kopecks % 100 == 0:
        return f"{int(rub):,}".replace(",", " ") + " ₽"
    return f"{rub:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def kk(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}кк"
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",") + "кк"


def num(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def parse_float(text: str) -> float | None:
    t = (text or "").strip().lower().replace(",", ".").replace("кк", "").replace("к", "").strip()
    if not t:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return v if v > 0 else None


def parse_money(text: str) -> int | None:
    """'1500' / '1500₽' / '1 500' -> копейки."""
    t = "".join(ch for ch in (text or "") if ch.isdigit())
    if not t:
        return None
    v = int(t)
    return v * 100 if v > 0 else None


GAME_TITLES = {
    "majestic": "Majestic RP",
    "russia": "Россия Онлайн",
}

GAME_EMOJI = {
    "majestic": "🏙",
    "russia": "🇷🇺",
}


def game_title(code: str) -> str:
    return GAME_TITLES.get(code, code)


def game_emoji(code: str) -> str:
    return GAME_EMOJI.get(code, "🎮")
