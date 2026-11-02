"""Конфигурация бота. Значения читаются из .env рядом с bot.py."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _parse_ids(raw: str) -> list[int]:
    out: list[int] = []
    for chunk in (raw or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk.lstrip("-").isdigit():
            out.append(int(chunk))
    return out


def _env_int(key: str, default: int) -> int:
    raw = (os.getenv(key, "") or "").strip()
    return int(raw) if raw.lstrip("-").isdigit() else default


def _env_float(key: str, default: float) -> float:
    raw = (os.getenv(key, "") or "").strip().replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class Config:
    token: str = os.getenv("BOT_TOKEN", "").strip()
    admins: list[int] = field(default_factory=lambda: _parse_ids(os.getenv("ADMIN_IDS", "")))
    bot_username: str = os.getenv("BOT_USERNAME", "BuyVirtssbot").strip().lstrip("@")

    pay_details: str = os.getenv("PAY_DETAILS", "СБП / карта — реквизиты выдаёт оператор").strip()
    pay_crypto: str = os.getenv("PAY_CRYPTO", "USDT TRC-20 — реквизиты выдаёт оператор").strip()
    support: str = os.getenv("SUPPORT", "@support").strip()
    shop_name: str = os.getenv("SHOP_NAME", "Вирты Маджестик").strip()
    currency: str = os.getenv("CURRENCY", "₽").strip() or "₽"

    min_topup: int = _env_int("MIN_TOPUP", 100)
    min_kk: float = _env_float("MIN_KK", 1.0)
    bonus_percent: int = _env_int("TOPUP_BONUS", 0)
    referral_percent: int = _env_int("REFERRAL_PERCENT", 3)
    welcome_bonus: int = _env_int("WELCOME_BONUS", 0)

    webapp_host: str = os.getenv("WEBAPP_HOST", "0.0.0.0").strip()
    webapp_port: int = _env_int("WEBAPP_PORT", 8080)
    webapp_url: str = os.getenv("WEBAPP_URL", "").strip()
    telegram_ip: str = os.getenv("TELEGRAM_IP", "").strip()
    proxy_url: str = os.getenv("PROXY_URL", "").strip()
    proxy_file: str = os.getenv("PROXY_FILE", "").strip()
    proxy_target: int = _env_int("PROXY_TARGET", 30)
    proxy_refresh_min: int = _env_int("PROXY_REFRESH_MIN", 25)
    net_retries: int = _env_int("NET_RETRIES", 4)
    net_timeout: int = _env_int("NET_TIMEOUT", 30)
    page_url: str = os.getenv("PAGE_URL", "https://buyvirtss.t.me").strip()

    db_path: Path = BASE_DIR / "data" / "bot.db"
    webapp_dir: Path = BASE_DIR / "webapp"

    @property
    def pay_block(self) -> str:
        return self.pay_details


CFG = Config()
