from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from urllib.parse import parse_qsl

from aiohttp import web

import db
import keyboards as kb
from config import CFG
from utils import game_title, money

log = logging.getLogger(__name__)

MAX_INIT_AGE = 24 * 3600  # initData живёт сутки


# ---------------------------------------------------------------- rate limit
@web.middleware
async def rate_limit_middleware(request: web.Request, handler):
    """Rate limit по IP: максимум 10 запросов в минуту на API endpoints."""
    path = request.path
    # Rate limit только для API endpoints
    if not path.startswith("/api/"):
        return await handler(request)
    
    ip = request.remote or "unknown"
    now = time.time()
    
    # Простая in-memory rate limit (для продакшена нужен Redis)
    if not hasattr(request.app, "_rate_limits"):
        request.app._rate_limits = {}
        request.app._rate_limits_cleanup = now
    
    key = f"rate_limit:{ip}"
    if key in request.app._rate_limits:
        timestamps = request.app._rate_limits[key]
        # очистить старые (старше 60 сек)
        timestamps = [t for t in timestamps if now - t < 60]
        if timestamps:
            request.app._rate_limits[key] = timestamps
        else:
            del request.app._rate_limits[key]  # ← FIX: Cleanup empty keys
    else:
        request.app._rate_limits[key] = [now]
    
    # Полная очистка каждые 5 минут (FIX: Memory leak prevention)
    if now - request.app._rate_limits_cleanup > 300:
        request.app._rate_limits = {
            k: [t for t in v if now - t < 60]
            for k, v in request.app._rate_limits.items()
        }
        request.app._rate_limits = {k: v for k, v in request.app._rate_limits.items() if v}
        request.app._rate_limits_cleanup = now
        log.debug("Rate limit cleanup: %d IPs tracked", len(request.app._rate_limits))
    
    # Check rate limit AFTER cleanup
    if key in request.app._rate_limits and len(request.app._rate_limits[key]) >= 10:
        return web.json_response({"detail": "Too many requests"}, status=429)
    
    return await handler(request)


# ---------------------------------------------------------------- проверка
def verify_init_data(init_data: str) -> dict | None:
    """Проверяет подпись Telegram WebApp initData. Возвращает данные user или None."""
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = pairs.pop("hash", "")
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", CFG.token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        return None

    # защита от повторного использования старой подписи
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        auth_date = 0
    if auth_date and (time.time() - auth_date) > MAX_INIT_AGE:
        return None

    try:
        return json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        return None


def current_user(request: web.Request):
    tg_user = verify_init_data(request.headers.get("X-Init-Data", ""))
    if not tg_user or not tg_user.get("id"):
        return None
    return db.ensure_user(
        int(tg_user["id"]),
        tg_user.get("username"),
        " ".join(filter(None, [tg_user.get("first_name"), tg_user.get("last_name")])),
    )


def require_user(handler):
    async def wrapper(request: web.Request):
        user = current_user(request)
        if user is None:
            return web.json_response({"detail": "Открой приложение через Telegram"}, status=401)
        request["user"] = user
        return await handler(request)

    return wrapper


# ------------------------------------------------------------------- api
@require_user
async def api_shop(request: web.Request) -> web.Response:
    user = request["user"]
    avg, count, _ = db.review_summary()
    servers = []
    for r in db.servers():
        short = r["name"].split()[0] if r["name"].startswith("N") else r["name"][:3]
        servers.append({
            "id": r["id"],
            "game": r["game"],
            "name": r["name"],
            "short": short,
            "price": r["price_kk"],
            "stock": r["stock_kk"],
        })
    return web.json_response({
        "balance": user["balance"],
        "shop_name": CFG.shop_name,
        "servers": servers,
        "rating": {"avg": avg, "count": count},
    })


@require_user
async def api_reviews(request: web.Request) -> web.Response:
    avg, count, dist = db.review_summary()
    items = []
    for r in db.reviews(status="published", limit=30):
        items.append({
            "id": r["id"],
            "rating": r["rating"],
            "text": r["text"],
            "reply": r["reply"],
            "who": (f"@{r['username']}" if r["username"] else (r["full_name"] or "Игрок")),
            "server": r["server_name"] or "",
            "date": r["created_at"][:10],
        })
    return web.json_response({
        "items": items,
        "summary": {"avg": avg, "count": count, "dist": dist},
    })


@require_user
async def api_me(request: web.Request) -> web.Response:
    user = request["user"]
    orders = [
        {
            "id": o["id"], "server": o["server_name"], "kk": o["kk"],
            "total": o["total"], "status": kb.order_status_label(o["status"]),
            "date": o["created_at"][:10],
        }
        for o in db.user_orders(user["id"], limit=10)
    ]
    return web.json_response({
        "id": user["tg_id"],
        "name": user["full_name"],
        "username": user["username"],
        "balance": user["balance"],
        "orders": orders,
    })


@require_user
async def api_order(request: web.Request) -> web.Response:
    user = request["user"]
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"detail": "Некорректный запрос"}, status=400)

    try:
        server_id = int(body.get("server_id", 0))
        if server_id <= 0:
            return web.json_response({"detail": "Некорректный сервер"}, status=400)
        
        amount_kk = float(str(body.get("kk", "0")).replace(",", "."))
        if amount_kk <= 0:
            return web.json_response({"detail": "Количество должно быть положительным"}, status=400)
        if amount_kk > 1_000_000:  # FIX: MAX limit
            return web.json_response({"detail": "Слишком много кк за раз"}, status=400)
    except (TypeError, ValueError):
        return web.json_response({"detail": "Некорректные параметры"}, status=400)

    nick = (body.get("nick") or "").strip()
    if len(nick) < 2 or len(nick) > 32:
        return web.json_response({"detail": "Ник: от 2 до 32 символов"}, status=400)
    if not nick.isprintable():  # FIX: Check for invisible chars
        return web.json_response({"detail": "Ник содержит недопустимые символы"}, status=400)

    r = db.server(server_id)
    if not r or not r["active"]:
        return web.json_response({"detail": "Сервер недоступен"}, status=400)
    if amount_kk < CFG.min_kk:
        return web.json_response({"detail": f"Минимум {CFG.min_kk:g}кк"}, status=400)
    if amount_kk > r["stock_kk"]:
        return web.json_response({"detail": f"В наличии только {r['stock_kk']:g}кк"}, status=400)

    total = int(round(r["price_kk"] * amount_kk))
    oid = db.create_order(user["id"], server_id, amount_kk, total, nick)

    # баланса хватает — списываем сразу, иначе показываем реквизиты в боте
    pay_link = None
    if user["balance"] >= total:
        try:
            new_balance = db.add_balance(user["id"], -total)
            db.set_order_status(oid, "paid", "оплачен с баланса (Mini App)", paid_from="balance")
            db.change_stock(server_id, -amount_kk)
            log.info("Mini App: заказ %s оплачен с баланса", oid)
            return web.json_response({
                "order_id": oid, "balance": new_balance, "paid": True,
            })
        except ValueError:
            pass

    pay_link = f"https://t.me/{CFG.bot_username}?start=pay_{oid}"
    return web.json_response({
        "order_id": oid,
        "balance": user["balance"],
        "paid": False,
        "pay_link": pay_link,
        "total": total,
    })


@require_user
async def api_review_post(request: web.Request) -> web.Response:
    user = request["user"]
    if db.get_setting(f"review_once:{user['id']}", ""):
        return web.json_response({"detail": "Ты уже оставлял отзыв"}, status=400)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"detail": "Некорректный запрос"}, status=400)

    try:
        rating = int(body.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    if rating not in range(1, 6):
        return web.json_response({"detail": "Оценка от 1 до 5"}, status=400)

    text = (body.get("text") or "").strip()
    if len(text) < 5:
        return web.json_response({"detail": "Слишком короткий отзыв"}, status=400)

    rid = db.add_review(user["id"], rating, text[:900])
    db.set_setting(f"review_once:{user['id']}", str(rid))
    return web.json_response({"review_id": rid})


# ------------------------------------------------------------------ страницы
async def page_app(request: web.Request) -> web.Response:
    path = CFG.webapp_dir / "app.html"
    return web.FileResponse(path, headers={"Cache-Control": "no-cache"})


async def page_index(request: web.Request) -> web.Response:
    raise web.HTTPFound("/app")


async def page_health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "time": datetime.now().isoformat(timespec="seconds")})


def create_app() -> web.Application:
    # Ограничиваем размер запроса — защита от мусорных payload'ов
    app = web.Application(
        client_max_size=256 * 1024,
        middlewares=[rate_limit_middleware],  # ← ADD rate limit middleware
    )
    app.router.add_get("/", page_index)
    app.router.add_get("/app", page_app)
    app.router.add_get("/health", page_health)
    app.router.add_get("/api/shop", api_shop)
    app.router.add_get("/api/reviews", api_reviews)
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/order", api_order)
    app.router.add_post("/api/review", api_review_post)
    app.router.add_static("/static/", CFG.webapp_dir, show_index=False)
    return app


def run_webapp() -> None:
    logging.basicConfig(level=logging.INFO)
    web.run_app(create_app(), host=CFG.webapp_host, port=CFG.webapp_port, print=None)
