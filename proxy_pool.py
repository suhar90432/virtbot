"""Пул HTTP-прокси для обхода блокировки api.telegram.org.

Собирает прокси из публичных списков, проверяет их реальным запросом
к Bot API, держит список живых и отдаёт их по кругу.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import aiohttp

log = logging.getLogger("proxy")

LISTS = (
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
)


class ProxyPool:
    """Живые прокси + проверка доступности Telegram через них."""

    def __init__(self, token: str, store: Path, target: float = 30.0):
        self.token = token
        self.store = store
        self.target = target
        self.alive: list[str] = []
        self.dead: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._rr = 0
        self._session: aiohttp.ClientSession | None = None

    # ---------------------------------------------------------------- storage
    def load(self) -> None:
        if self.store.exists():
            try:
                data = json.loads(self.store.read_text(encoding="utf-8"))
                self.alive = [p for p in data.get("alive", []) if isinstance(p, str)]
                log.info("Загружено %s прокси из кэша", len(self.alive))
            except Exception:
                self.alive = []

    def save(self) -> None:
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            self.store.write_text(
                json.dumps({"alive": self.alive, "ts": int(time.time())}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ---------------------------------------------------------------- helpers
    @property
    def check_url(self) -> str:
        return f"https://api.telegram.org/bot{self.token}/getMe"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    limit=100,          # ← Было 300 - слишком много
                    limit_per_host=30,  # ← Добавлено: разумный лимит на хост
                    ttl_dns_cache=300,  # ← Кэш DNS 5 минут
                    ssl=False,
                    force_close=True,
                ),
            )
        return self._session

    async def check(self, proxy: str, timeout: float = 8.0) -> bool:
        try:
            session = await self._get_session()
            async with session.get(
                self.check_url,
                proxy=f"http://{proxy}",
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as r:
                if r.status != 200:
                    return False
                body = await r.json(content_type=None)
                return bool(body.get("ok"))
        except Exception:
            return False

    # ------------------------------------------------------------------ fetch
    async def download_candidates(self) -> list[str]:
        out: list[str] = []
        session = await self._get_session()
        for url in LISTS:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as r:
                    if r.status != 200:
                        continue
                    text = await r.text()
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.count(":") == 1 and line.split(":")[1].isdigit():
                        out.append(line)
            except Exception as e:
                log.debug("список %s недоступен: %s", url, e)
        return list(dict.fromkeys(out))

    async def verify_many(self, candidates: list[str], want: int | None = None) -> list[str]:
        """Проверяет пачками, возвращает живые. Потокобезопасно."""
        want = want or int(self.target)
        found: list[str] = []
        checked: set[str] = set()
        found_lock = asyncio.Lock()  # ← FIX: Защита от race condition
        sem = asyncio.Semaphore(200)
        queue = asyncio.Queue(maxsize=500)  # ← FIX: Bounded memory usage
        
        # Безопасно заполняем очередь
        for p in candidates:
            try:
                queue.put_nowait(p)
            except asyncio.QueueFull:
                log.warning("Proxy queue full, dropping candidate: %s", p)

        async def worker():
            while True:
                try:
                    proxy = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                
                if proxy in checked:
                    continue
                checked.add(proxy)
                
                async with sem:
                    if await self.check(proxy):
                        async with found_lock:  # ← FIX: Thread-safe append
                            if proxy not in found and len(found) < want:
                                found.append(proxy)
                                log.info("Прокси OK: %s (%s/%s)", proxy, len(found), want)
                                self.save()

        # Запускаем ровно столько workers, сколько надо
        worker_count = min(200, max(1, len(candidates)))
        await asyncio.gather(*[worker() for _ in range(worker_count)], return_exceptions=True)
        return found

    async def refresh(self, extra: list[str] | None = None) -> None:
        """Полный прогон: докачать списки, проверить, обновить пул."""
        async with self._lock:
            log.info("Обновляю пул прокси...")
            cands = extra or await self.download_candidates()
            now = time.time()
            cands = [p for p in cands if now - self.dead.get(p, 0) > 900]
            live = await self.verify_many(cands, want=int(self.target))
            if live:
                merged = list(dict.fromkeys(live + self.alive))
                self.alive = merged[: max(int(self.target) * 2, 40)]
            self.save()
            log.info("Пул прокси: %s живых", len(self.alive))

    async def recheck(self) -> None:
        """Быстрая перепроверка текущего пула, без скачивания списков."""
        async with self._lock:
            if not self.alive:
                return
            sem = asyncio.Semaphore(60)
            keep: list[str] = []

            async def one(p: str):
                async with sem:
                    if await self.check(p, timeout=6):
                        keep.append(p)
                    else:
                        self.dead[p] = time.time()

            await asyncio.gather(*[one(p) for p in list(self.alive)])
            if keep:
                self.alive = keep
                self.save()
                log.info("Перепроверка: осталось %s живых", len(keep))

    # --------------------------------------------------------------- rotation
    def next_proxy(self) -> str | None:
        if not self.alive:
            return None
        self._rr = (self._rr + 1) % len(self.alive)
        return self.alive[self._rr]

    def mark_dead(self, proxy: str | None) -> None:
        if not proxy:
            return
        self.dead[proxy] = time.time()
        if proxy in self.alive:
            self.alive.remove(proxy)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
