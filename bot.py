"""Точка входа: Telegram-бот + HTTP-сервер Mini App в одном процессе.

Провайдер режет api.telegram.org, поэтому все запросы идут через пул
живых прокси. Mini App поднимается первым и работает независимо от Telegram.
Ничего не падает: при обрыве бот переподключается сам.
"""
from __future__ import annotations

import asyncio
import logging
import random
import signal
import sys
import time
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat
from aiohttp import web
from logging.handlers import RotatingFileHandler

import db
from config import CFG
from handlers_admin import router as admin_router
from handlers_user import router as user_router
from pooled_session import PooledSession
from proxy_pool import ProxyPool
from webapp_server import create_app

LOG_FILE = CFG.db_path.parent / "bot.log"
log = logging.getLogger("bot")


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            RotatingFileHandler(
                LOG_FILE,
                encoding="utf-8",
                maxBytes=50 * 1024 * 1024,  # 50 MB per file
                backupCount=5,  # keep 5 files
            ),
        ],
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


async def start_webapp() -> web.AppRunner:
    runner = web.AppRunner(create_app())
    await runner.setup()
    site = web.TCPSite(runner, CFG.webapp_host, CFG.webapp_port)
    await site.start()
    log.info("Mini App на http://%s:%s/app", CFG.webapp_host, CFG.webapp_port)
    if CFG.webapp_url:
        log.info("Публичный адрес Mini App: %s/app", CFG.webapp_url)
    return runner


async def setup_commands(bot: Bot) -> None:
    base = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="menu", description="Меню"),
        BotCommand(command="app", description="Открыть магазин"),
        BotCommand(command="help", description="Помощь"),
    ]
    try:
        await bot.set_my_commands(base)
    except Exception as e:
        log.debug("set_my_commands: %s", e)
    for admin_id in CFG.admins:
        try:
            await bot.set_my_commands(
                base + [BotCommand(command="admin", description="Админ-панель")],
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception:
            pass


async def proxy_keeper(pool: ProxyPool) -> None:
    """Держит пул прокси наполненным: обновляет списки и перепроверяет.
    
    Разделено на два цикла, чтобы не было lock contention:
    - recheck: быстро (~30 сек), часто (каждые 10 минут)
    - refresh: медленно (~60+ сек), редко (когда мало живых)
    """
    # Первый прогон — обязательный, до него не стартуем.
    if not pool.alive:
        await pool.refresh()
    
    recheck_interval = CFG.proxy_refresh_min * 60  # 10 минут
    next_refresh = time.time()  # init to now
    backoff = 10.0  # exponential backoff
    
    while True:
        try:
            # Быстрая перепроверка живых прокси
            try:
                await asyncio.wait_for(pool.recheck(), timeout=45.0)
            except asyncio.TimeoutError:
                log.warning("recheck() заняло > 45 сек, пропускаю")
            
            # Каждый час или когда мало живых — полный refresh
            now = time.time()
            if now >= next_refresh or len(pool.alive) < 10:
                if len(pool.alive) < 10:
                    log.info("Мало живых прокси (%s), запускаю refresh", len(pool.alive))
                try:
                    await asyncio.wait_for(pool.refresh(), timeout=90.0)
                    next_refresh = now + 3600  # Не раньше чем через час
                    backoff = 10.0  # reset on success
                except asyncio.TimeoutError:
                    log.warning("refresh() заняло > 90 сек, пропускаю")
                    next_refresh = now + backoff
                    backoff = min(backoff * 1.5, 600.0)  # cap at 10 min
            
            await asyncio.sleep(recheck_interval)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("Ошибка обновления прокси: %s", e)
            await asyncio.sleep(30)


async def ensure_login(bot: Bot, pool: ProxyPool) -> bool:
    """Ждёт, пока getMe пройдёт через какой-нибудь прокси."""
    delay = 2.0
    while True:
        try:
            me = await bot.get_me()
            log.info("Связь с Telegram есть: @%s (прокси в пуле: %s)", me.username, len(pool.alive))
            return True
        except TelegramUnauthorizedError:
            log.error("Токен неверный или отозван — проверь BOT_TOKEN в .env")
            return False
        except Exception as e:
            log.warning("Telegram недоступен (%s), пробую снова через %.0f с", type(e).__name__, delay)
            if len(pool.alive) < 5:
                try:
                    await pool.refresh()
                except Exception:
                    pass
            await asyncio.sleep(delay + random.uniform(0, 1.0))
            delay = min(delay * 1.5, 30.0)


async def polling_supervisor(bot: Bot, dp: Dispatcher, pool: ProxyPool) -> None:
    """Держит polling живым: при падении перезапускает после восстановления связи.
    
    Также проверяет флаг перезагрузки из /restart endpoint и завершает цикл,
    позволяя Replit автоматически перезагрузить процесс.
    """
    delay = 3.0
    while True:
        try:
            if not await ensure_login(bot, pool):
                return
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except Exception:
                pass
            log.info("Запускаю polling")
            await dp.start_polling(bot, handle_signals=False, polling_timeout=15)
            log.warning("Polling завершился, перезапуск через 3 с")
            delay = 3.0
            await asyncio.sleep(3)
        except TelegramUnauthorizedError:
            log.error("Токен отклонён Telegram — polling остановлен.")
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("Polling упал: %s: %s. Перезапуск через %.0f с", type(e).__name__, e, delay)
            await asyncio.sleep(delay + random.uniform(0, 1.0))
            delay = min(delay * 1.6, 60.0)
            await asyncio.sleep(delay)
            delay = min(delay * 1.6, 60.0)


async def main() -> None:
    setup_logging()

    if not CFG.token or ":" not in CFG.token:
        log.error("BOT_TOKEN не задан. Открой .env и вставь токен от @BotFather.")
        return
    if not CFG.admins:
        log.warning("ADMIN_IDS пуст — админ-панель будет недоступна.")

    if not CFG.restart_secret:
        log.warning("RESTART_SECRET не задан в .env — endpoint /restart будет заблокирован")

    db.init_db()
    runner = await start_webapp()
    app = runner.app  # ← Получаем ссылку на webapp для проверки флага перезагрузки

    pool = ProxyPool(CFG.token, CFG.db_path.parent / "proxies.json", target=CFG.proxy_target)
    pool.load()
    keeper = asyncio.create_task(proxy_keeper(pool))

    session = PooledSession(
        pool,
        attempts=4,
        # Важно: именно число. aiogram прибавляет к нему polling_timeout.
        timeout=float(CFG.net_timeout),
    )
    bot = Bot(
        token=CFG.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(user_router)

    try:
        if await ensure_login(bot, pool):
            log.info("Бот @%s запущен (%s)", CFG.bot_username, datetime.now().strftime("%d.%m.%Y %H:%M"))
            await setup_commands(bot)
            for admin_id in CFG.admins:
                try:
                    await asyncio.wait_for(
                        bot.send_message(admin_id, "🟢 Бот запущен и готов к работе."),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    log.warning("send_message timeout для админа %s", admin_id)
                except Exception:
                    pass
            
            # Запускаем polling с проверкой флага перезагрузки
            while not app.get("restart_requested", False):
                await polling_supervisor(bot, dp, pool)
                if app.get("restart_requested", False):
                    log.info("Restart requested — останавливаю polling и завершаю процесс")
                    break
                await asyncio.sleep(1)  # Небольшая пауза перед следующим cycle
        else:
            log.error("Запуск отменён: не удалось авторизоваться в Telegram.")
    finally:
        db.close_all_connections()  # ← NEW: cleanup DB connections
        keeper.cancel()
        await runner.cleanup()
        await session.close()
        await pool.close()


if __name__ == "__main__":
    def handle_sigterm(sig, frame):
        log.info("Получен SIGTERM, завершаюсь...")
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)
    
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Graceful shutdown completed.")
