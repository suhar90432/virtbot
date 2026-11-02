"""Единый визуальный стиль: зелёная палитра, эмодзи, оформление карточек."""
from __future__ import annotations

# ---------------------------------------------------------------- палитра
GREEN = "🟢"
LEAF = "🌿"          # хвойно-зелёный акцент
MONEY = "💚"
CHECK = "✅"
WARN = "⚠️"
FIRE = "🔥"
DIAMOND = "💎"
STAR = "⭐"
CROWN = "👑"

# разделители для «зелёного» вида карточек
LINE = "━━━━━━━━━━━━━━━━━━"
THIN = "─────────────"


def stars(rating: int) -> str:
    rating = max(0, min(5, int(rating)))
    return "★" * rating + "☆" * (5 - rating)


def stars_emoji(rating: int) -> str:
    rating = max(0, min(5, int(rating)))
    return "⭐" * rating + "☆" * (5 - rating)


def bar(value: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "░" * width
    filled = int(round(value / total * width))
    return "█" * filled + "░" * (width - filled)


def header(title: str, subtitle: str = "") -> str:
    out = f"{LEAF} <b>{title}</b> {LEAF}"
    if subtitle:
        out += f"\n<i>{subtitle}</i>"
    return out


def card(title: str, rows: list[tuple[str, str]], footer: str = "") -> str:
    """Карточка в стиле: заголовок + пары ключ-значение + подвал."""
    lines = [f"{LEAF} <b>{title}</b>", THIN]
    for k, v in rows:
        lines.append(f"{k}  {v}")
    if footer:
        lines.append(THIN)
        lines.append(footer)
    return "\n".join(lines)
