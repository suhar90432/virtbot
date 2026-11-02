"""Ищет рабочий HTTP/HTTPS-прокси, через который доступен api.telegram.org."""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import aiohttp

TOKEN = "9214718186:AAHSBQitW3HpEOfqhV6R4QTQ9cjw-BgAgsY"
URL = f"https://api.telegram.org/bot{TOKEN}/getMe"


def load(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and ":" in line and not line.startswith("#"):
            out.append(line)
    return out


async def check(session: aiohttp.ClientSession, proxy: str, sem: asyncio.Semaphore):
    async with sem:
        try:
            async with session.get(
                URL, proxy=f"http://{proxy}", timeout=aiohttp.ClientTimeout(total=9)
            ) as r:
                if r.status == 200:
                    body = await r.json()
                    if body.get("ok"):
                        return proxy, body["result"].get("username")
        except Exception:
            return None
    return None


async def main() -> None:
    files = sorted(Path.home().glob("../../AppData/Local/Temp/proxies_*.txt"))
    tmp = Path("C:/Users/ckanu/AppData/Local/Temp")
    cands: list[str] = []
    for p in tmp.glob("proxies_*.txt"):
        cands += load(p)
    cands = list(dict.fromkeys(cands))
    print(f"кандидатов: {len(cands)}", flush=True)

    connector = aiohttp.TCPConnector(limit=250, ssl=False, force_close=True)
    sem = asyncio.Semaphore(250)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check(session, p, sem) for p in cands]
        found = []
        t0 = time.time()
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            res = await coro
            if res:
                proxy, user = res
                print(f"[{i}] РАБОЧИЙ {proxy} -> @{user}", flush=True)
                found.append(proxy)
                if len(found) >= 8:
                    break
            if i % 500 == 0:
                print(f"...проверено {i}, прошло {time.time()-t0:.0f} c", flush=True)
    print("ИТОГ:", found)


if __name__ == "__main__":
    asyncio.run(main())
