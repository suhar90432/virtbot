"""Сессия aiogram, которая ходит в Telegram через пул прокси.

Провайдер режет api.telegram.org напрямую, поэтому запросы идут через
HTTP-прокси из пула. Сессия «прилипает» к одному рабочему прокси
и меняет его только при обрыве — так polling не дёргается зря.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import aiohttp
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType

from proxy_pool import ProxyPool

log = logging.getLogger("session")


class PooledSession(AiohttpSession):
    """Каждый запрос — через живой прокси; при сбое берём следующий."""

    def __init__(self, pool: ProxyPool, attempts: int = 6, **kwargs: Any) -> None:
        # aiogram ждёт в timeout число (он складывает его с polling_timeout),
        # поэтому ClientTimeout здесь недопустим — приводим к float.
        raw = kwargs.get("timeout")
        if isinstance(raw, aiohttp.ClientTimeout):
            kwargs["timeout"] = float(raw.total or 30.0)
        super().__init__(**kwargs)
        self.pool = pool
        self.attempts = attempts
        self._sticky: str | None = None

    def _attempt_timeout(self, request_timeout: float) -> aiohttp.ClientTimeout:
        # Дохлый прокси должен отваливаться быстро по коннекту,
        # а на чтение даём полный бюджет (нужен для long polling).
        return aiohttp.ClientTimeout(
            total=request_timeout,
            connect=min(8.0, request_timeout),
            sock_read=request_timeout,
        )

    def _pick(self) -> str | None:
        if self._sticky and self._sticky in self.pool.alive:
            return self._sticky
        self._sticky = self.pool.next_proxy()
        return self._sticky

    def _drop(self, proxy: str | None) -> None:
        if proxy and proxy == self._sticky:
            self._sticky = None
        self.pool.mark_dead(proxy)

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        session = await self.create_session()
        url = self.api.api_url(token=bot.token, method=method.__api_method__)
        form = self.build_form_data(bot=bot, method=method)
        request_timeout = float(self.timeout if timeout is None else timeout)
        attempt_timeout = self._attempt_timeout(request_timeout)

        last: Exception | None = None
        for attempt in range(1, self.attempts + 1):
            proxy = self._pick()
            try:
                async with session.post(
                    url,
                    data=form,
                    timeout=attempt_timeout,
                    proxy=f"http://{proxy}" if proxy else None,
                ) as resp:
                    raw = await resp.text()
                # Ответ пришёл — прокси рабочий, дальше идём через него же.
                response = self.check_response(
                    bot=bot,
                    method=method,
                    status_code=resp.status,
                    content=raw,
                )
                return cast(TelegramType, response.result)
            except TelegramNetworkError as e:
                last = e
                self._drop(proxy)
                log.debug("%s: прокси %s не сработал (%s/%s)", method.__api_method__, proxy, attempt, self.attempts)
            except asyncio.TimeoutError as e:
                last = e
                self._drop(proxy)
                log.debug("%s: таймаут через %s (%s/%s)", method.__api_method__, proxy, attempt, self.attempts)
            except aiohttp.ClientError as e:
                last = e
                self._drop(proxy)
                log.debug("%s: ошибка %s через %s", method.__api_method__, type(e).__name__, proxy)

            await asyncio.sleep(0.2)

        if last is None:
            raise TelegramNetworkError(method=method, message="нет доступных прокси")
        if isinstance(last, TelegramNetworkError):
            raise last
        raise TelegramNetworkError(method=method, message=f"{type(last).__name__}: {last}") from last
