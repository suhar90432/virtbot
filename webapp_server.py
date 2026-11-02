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


def get_embedded_app_html() -> str:
    """Embedded Mini App HTML for when webapp/app.html is not available."""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VirtBot Mini App</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #0a0e27 0%, #1a1a3e 100%);
            color: #00ff41;
            min-height: 100vh;
            padding: 10px;
            overflow-x: hidden;
        }
        .container {
            max-width: 500px;
            margin: 0 auto;
            background: rgba(10, 14, 39, 0.95);
            border: 2px solid #00ff41;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 0 30px rgba(0, 255, 65, 0.3), inset 0 0 20px rgba(0, 255, 65, 0.05);
        }
        h1 {
            color: #00ff41;
            text-align: center;
            font-size: 28px;
            margin-bottom: 5px;
            text-shadow: 0 0 10px #00ff41, 0 0 20px rgba(0, 255, 65, 0.5);
            animation: glow-pulse 2s ease-in-out infinite;
        }
        @keyframes glow-pulse {
            0%, 100% { text-shadow: 0 0 10px #00ff41, 0 0 20px rgba(0, 255, 65, 0.5); }
            50% { text-shadow: 0 0 20px #00ff41, 0 0 40px rgba(0, 255, 65, 0.8); }
        }
        .subtitle { color: #00cc33; text-align: center; font-size: 12px; margin-bottom: 20px; opacity: 0.8; }
        .section { margin-bottom: 25px; }
        .section-title {
            color: #00ff41;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(0, 255, 65, 0.3);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .project-selector { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .project-btn {
            padding: 12px;
            border: 2px solid #00ff41;
            background: rgba(0, 255, 65, 0.05);
            color: #00ff41;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            font-size: 12px;
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .project-btn:hover { background: rgba(0, 255, 65, 0.15); box-shadow: 0 0 15px rgba(0, 255, 65, 0.5); }
        .project-btn.active { background: linear-gradient(135deg, #00ff41 0%, #00cc33 100%); color: #0a0e27; box-shadow: 0 0 20px rgba(0, 255, 65, 0.8), inset 0 0 10px rgba(0, 255, 65, 0.3); }
        .input-group { margin-bottom: 15px; }
        .input-label { color: #00ff41; font-size: 13px; font-weight: bold; margin-bottom: 6px; display: block; text-transform: uppercase; letter-spacing: 0.5px; }
        .input-wrapper { display: flex; gap: 8px; align-items: center; }
        .quantity-input { flex: 1; padding: 10px; border: 2px solid #00ff41; background: rgba(0, 255, 65, 0.05); color: #00ff41; border-radius: 6px; font-size: 14px; font-weight: bold; transition: all 0.3s; }
        .quantity-input:focus { outline: none; background: rgba(0, 255, 65, 0.1); box-shadow: 0 0 15px rgba(0, 255, 65, 0.5); }
        .quantity-input::placeholder { color: rgba(0, 255, 65, 0.5); }
        .unit { color: #00cc33; font-size: 11px; font-weight: bold; min-width: 60px; padding: 10px; background: rgba(0, 255, 65, 0.05); border: 1px solid rgba(0, 255, 65, 0.3); border-radius: 6px; text-align: center; }
        .server-list { max-height: 280px; overflow-y: auto; border: 1px solid rgba(0, 255, 65, 0.3); border-radius: 8px; padding: 0; }
        .server-item { padding: 12px; border: 2px solid rgba(0, 255, 65, 0.3); background: rgba(0, 255, 65, 0.02); border-radius: 8px; cursor: pointer; margin-bottom: 8px; transition: all 0.3s; display: flex; justify-content: space-between; align-items: center; }
        .server-name { color: #00ff41; font-weight: 600; font-size: 13px; }
        .server-details { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
        .server-price { color: #00cc33; font-weight: bold; font-size: 12px; }
        .server-stock { color: #00ff41; font-size: 10px; opacity: 0.8; }
        .server-item:hover { background: rgba(0, 255, 65, 0.1); border-color: rgba(0, 255, 65, 0.6); box-shadow: 0 0 10px rgba(0, 255, 65, 0.3); }
        .server-item.active { background: rgba(0, 255, 65, 0.15); border-color: #00ff41; box-shadow: 0 0 15px rgba(0, 255, 65, 0.5), inset 0 0 5px rgba(0, 255, 65, 0.1); }
        .info-block { background: rgba(0, 255, 65, 0.08); border: 1px solid rgba(0, 255, 65, 0.3); border-radius: 8px; padding: 12px; margin-bottom: 15px; font-size: 12px; color: #00ff41; }
        .info-row { display: flex; justify-content: space-between; margin: 6px 0; }
        .info-label { opacity: 0.7; }
        .info-value { font-weight: bold; color: #00ff41; }
        .total-price { background: linear-gradient(135deg, rgba(0, 255, 65, 0.1) 0%, rgba(0, 204, 51, 0.05) 100%); border: 2px solid #00ff41; border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 15px; }
        .total-label { color: #00cc33; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
        .total-value { color: #00ff41; font-size: 28px; font-weight: bold; text-shadow: 0 0 10px #00ff41; }
        .currency { font-size: 16px; opacity: 0.8; }
        .checkout-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #00ff41 0%, #00cc33 100%); color: #0a0e27; border: 2px solid #00ff41; border-radius: 8px; font-size: 14px; font-weight: bold; cursor: pointer; transition: all 0.3s; text-transform: uppercase; letter-spacing: 1px; box-shadow: 0 0 20px rgba(0, 255, 65, 0.4); }
        .checkout-btn:hover:not(:disabled) { box-shadow: 0 0 30px rgba(0, 255, 65, 0.8); transform: translateY(-2px); }
        .checkout-btn:active:not(:disabled) { transform: translateY(0); }
        .checkout-btn:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: rgba(0, 255, 65, 0.05); border-radius: 3px; }
        ::-webkit-scrollbar-thumb { background: rgba(0, 255, 65, 0.3); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(0, 255, 65, 0.5); }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ VIRTBOT</h1>
        <div class="subtitle">Приобретите виртуальную валюту</div>
        <div class="section">
            <div class="section-title">🎮 Шаг 1: Выберите проект</div>
            <div class="project-selector">
                <button class="project-btn active" onclick="selectProject('russia', this)">Россия Онлайн</button>
                <button class="project-btn" onclick="selectProject('majestic', this)">Majestic RP</button>
            </div>
        </div>
        <div class="section">
            <div class="input-group">
                <label class="input-label">📊 Шаг 2: Количество</label>
                <div class="input-wrapper">
                    <input type="number" class="quantity-input" id="virtInput" placeholder="Введите количество" onchange="updateCalculation()" oninput="updateCalculation()" min="1">
                    <div class="unit">тыс.</div>
                </div>
            </div>
        </div>
        <div class="section">
            <div class="section-title">🌍 Шаг 3: Выберите сервер</div>
            <div class="server-list" id="serverList"></div>
        </div>
        <div class="info-block">
            <div class="info-row"><span class="info-label">Проект:</span><span class="info-value" id="selectedProject">Россия Онлайн</span></div>
            <div class="info-row"><span class="info-label">Количество:</span><span class="info-value" id="selectedQuantity">-</span></div>
            <div class="info-row"><span class="info-label">Сервер:</span><span class="info-value" id="selectedServer">Не выбран</span></div>
        </div>
        <div class="total-price">
            <div class="total-label">Итого к оплате</div>
            <div class="total-value"><span id="totalPrice">0</span><span class="currency"> ₽</span></div>
        </div>
        <button class="checkout-btn" onclick="checkout()" id="checkoutBtn" disabled>✅ Оформить заказ</button>
    </div>
    <script>
        const servers = [
            { name: "№01 New York", price: 0.840, stock: 384 },
            { name: "№02 Detroit", price: 0.390, stock: 217 },
            { name: "№03 Chicago", price: 0.370, stock: 463 },
            { name: "№04 San Francisco", price: 0.230, stock: 291 },
            { name: "№05 Atlanta", price: 0.280, stock: 176 },
            { name: "№06 San Diego", price: 0.310, stock: 428 },
            { name: "№07 Los Angeles", price: 0.310, stock: 352 },
            { name: "№08 Miami", price: 0.300, stock: 249 },
            { name: "№09 Las Vegas", price: 0.240, stock: 491 },
            { name: "№10 Washington", price: 0.230, stock: 318 },
            { name: "№11 Dallas", price: 0.370, stock: 203 },
            { name: "№12 Boston", price: 0.310, stock: 447 },
            { name: "№13 Houston", price: 0.540, stock: 269 },
            { name: "№14 Seattle", price: 0.290, stock: 376 },
            { name: "№15 Phoenix", price: 0.290, stock: 158 },
            { name: "№16 Denver", price: 0.300, stock: 412 },
            { name: "№17 Portland", price: 0.300, stock: 326 },
            { name: "№18 Orlando", price: 0.480, stock: 184 },
            { name: "№19 Memphis", price: 0.490, stock: 475 },
            { name: "Russia.online Тверской", price: 0.600, stock: 186 },
            { name: "Russia.online Кутузовский", price: 0.540, stock: 273 },
            { name: "Russia.online Арбатский", price: 0.490, stock: 224 }
        ];
        let selectedProject = 'russia';
        let selectedServer = null;
        let selectedQuantity = 0;
        let TelegramWebApp = window.Telegram?.WebApp;
        if (TelegramWebApp) { TelegramWebApp.ready(); TelegramWebApp.expand(); }
        function renderServers() {
            const list = document.getElementById('serverList');
            list.innerHTML = servers.map((server, index) => `
                <div class="server-item" onclick="selectServer(${index}, this)">
                    <span class="server-name">${server.name}</span>
                    <div class="server-details">
                        <span class="server-price">${server.price.toFixed(2)} ₽</span>
                        <span class="server-stock">Наличие: ${server.stock}кк</span>
                    </div>
                </div>
            `).join('');
        }
        function selectProject(project, btn) {
            selectedProject = project;
            selectedServer = null;
            document.querySelectorAll('.project-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('selectedProject').textContent = project === 'russia' ? 'Россия Онлайн' : 'Majestic RP';
            document.querySelectorAll('.server-item').forEach(item => item.classList.remove('active'));
            updateCalculation();
        }
        function selectServer(index, element) {
            selectedServer = index;
            document.querySelectorAll('.server-item').forEach(item => item.classList.remove('active'));
            element.classList.add('active');
            document.getElementById('selectedServer').textContent = servers[index].name;
            updateCalculation();
        }
        function updateCalculation() {
            const input = document.getElementById('virtInput').value.trim();
            if (!input) {
                selectedQuantity = 0;
                document.getElementById('selectedQuantity').textContent = '-';
                document.getElementById('totalPrice').textContent = '0';
                document.getElementById('checkoutBtn').disabled = true;
                return;
            }
            const quantity = parseInt(input) || 0;
            if (quantity < 1) {
                document.getElementById('totalPrice').textContent = '0';
                document.getElementById('checkoutBtn').disabled = true;
                return;
            }
            selectedQuantity = quantity;
            document.getElementById('selectedQuantity').textContent = quantity + ' тыс.';
            if (selectedServer !== null) {
                const server = servers[selectedServer];
                const totalPrice = server.price * quantity;
                document.getElementById('totalPrice').textContent = totalPrice.toFixed(2);
                document.getElementById('checkoutBtn').disabled = false;
            } else {
                document.getElementById('totalPrice').textContent = '0';
                document.getElementById('checkoutBtn').disabled = true;
            }
        }
        function checkout() {
            if (selectedQuantity < 1) {
                alert('Введите количество!');
                return;
            }
            if (selectedServer === null) {
                alert('Пожалуйста, выберите сервер!');
                return;
            }
            const server = servers[selectedServer];
            const nick = prompt('Введите имя персонажа (2-32 символа):');
            if (!nick || nick.length < 2 || nick.length > 32) {
                alert('Неверное имя персонажа!');
                return;
            }
            const payload = {
                server_id: selectedServer + 1,
                kk: selectedQuantity,
                nick: nick,
                project: selectedProject
            };
            if (window.Telegram && window.Telegram.WebApp) {
                window.Telegram.WebApp.sendData(JSON.stringify(payload));
            } else {
                alert('Ошибка: Откройте приложение через Telegram!');
            }
        }
        renderServers();
    </script>
</body>
</html>"""


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
    
    # Fallback: serve inline if file doesn't exist (e.g., Replit hasn't synced from GitHub yet)
    if not path.exists():
        log.warning("app.html not found at %s, serving inline Mini App", path)
        html = get_embedded_app_html()
        return web.Response(text=html, content_type='text/html', headers={"Cache-Control": "no-cache"})
    
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
