"""Слой данных: SQLite + простые хелперы. Все суммы — в копейках (int)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable

from catalog import SEED_SERVERS
from config import CFG

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    tg_id       INTEGER UNIQUE NOT NULL,
    username    TEXT,
    full_name   TEXT,
    balance     INTEGER NOT NULL DEFAULT 0,
    is_blocked  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS servers (
    id           INTEGER PRIMARY KEY,
    game         TEXT NOT NULL,
    name         TEXT NOT NULL,
    price_kk     INTEGER NOT NULL,           -- копеек за 1 кк (1 000 000 виртов)
    stock_kk     REAL NOT NULL DEFAULT 0,
    active       INTEGER NOT NULL DEFAULT 1,
    sort         INTEGER NOT NULL DEFAULT 0,
    UNIQUE(game, name)
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    server_id   INTEGER NOT NULL,
    kk          REAL NOT NULL,
    total       INTEGER NOT NULL,
    nick        TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'new',
    paid_from   TEXT NOT NULL DEFAULT '',
    comment     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topups (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    amount      INTEGER NOT NULL,
    method      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    order_id    INTEGER,
    rating      INTEGER NOT NULL,
    text        TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'published',
    reply       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promos (
    id           INTEGER PRIMARY KEY,
    code         TEXT UNIQUE NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'percent',   -- percent | fixed
    value        INTEGER NOT NULL,                  -- проценты или копейки
    max_uses     INTEGER NOT NULL DEFAULT 0,        -- 0 = без лимита
    used         INTEGER NOT NULL DEFAULT 0,
    min_total    INTEGER NOT NULL DEFAULT 0,
    active       INTEGER NOT NULL DEFAULT 1,
    expires_at   TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_uses (
    id        INTEGER PRIMARY KEY,
    promo_id  INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    order_id  INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(promo_id, order_id)
);

CREATE TABLE IF NOT EXISTS referrals (
    id          INTEGER PRIMARY KEY,
    referrer_id INTEGER NOT NULL,      -- users.id кто позвал
    invited_id  INTEGER NOT NULL UNIQUE,
    earned      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reviews_stat ON reviews(status);
CREATE INDEX IF NOT EXISTS idx_orders_user  ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_stat  ON orders(status);
CREATE INDEX IF NOT EXISTS idx_topups_stat  ON topups(status);
CREATE INDEX IF NOT EXISTS idx_ref_referrer ON referrals(referrer_id);
"""

# Validation for order statuses — prevent injection attacks
ALLOWED_ORDER_STATUSES = {"new", "paid", "delivering", "done", "cancelled"}

MIGRATIONS = {
    "users": {
        "referrer_id": "INTEGER",
        "ref_code": "TEXT",
        "notify": "INTEGER NOT NULL DEFAULT 1",
    },
    "orders": {
        "promo_id": "INTEGER",
        "discount": "INTEGER NOT NULL DEFAULT 0",
        "reviewed": "INTEGER NOT NULL DEFAULT 0",
        "ref_bonus": "INTEGER NOT NULL DEFAULT 0",
    },
}

ORDER_FLOW = {
    "new": "Новый",
    "paid": "Оплачен",
    "delivering": "Выдаётся",
    "done": "Выполнен",
    "cancelled": "Отменён",
}


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect():
    CFG.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CFG.db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as c:
        c.executescript(SCHEMA)
        # миграции: добавляем недостающие колонки в старую базу
        for table, cols in MIGRATIONS.items():
            have = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
            for col, ddl in cols.items():
                if col not in have:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        existing = {(r["game"], r["name"]) for r in c.execute("SELECT game, name FROM servers")}
        for i, (game, name, price_k, stock) in enumerate(SEED_SERVERS):
            price_kk = round(float(price_k) * 1000 * 100)  # ₽/1к -> коп/1кк
            if (game, name) in existing:
                continue
            c.execute(
                "INSERT INTO servers (game, name, price_kk, stock_kk, sort) VALUES (?,?,?,?,?)",
                (game, name, price_kk, stock, i),
            )


# ---------------------------------------------------------------- users
def get_user(tg_id: int) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()


def ensure_user(tg_id: int, username: str | None, full_name: str | None) -> sqlite3.Row:
    with connect() as c:
        c.execute(
            "INSERT INTO users (tg_id, username, full_name, created_at) VALUES (?,?,?,?) "
            "ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
            (tg_id, username or "", full_name or "", now()),
        )
        row = c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
        if row and not row["ref_code"]:
            code = f"ref{row['id']}"
            c.execute("UPDATE users SET ref_code=? WHERE id=?", (code, row["id"]))
            row = c.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
        return row


def user_by_id(uid: int) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def add_balance(uid: int, delta: int) -> int:
    """Атомарно меняет баланс, возвращает новый. Отрицательный результат -> ValueError."""
    with connect() as c:
        row = c.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()
        if row is None:
            raise ValueError("user not found")
        new_balance = row["balance"] + delta
        if new_balance < 0:
            raise ValueError("insufficient funds")
        c.execute("UPDATE users SET balance=? WHERE id=?", (new_balance, uid))
        return new_balance


def set_blocked(uid: int, blocked: bool) -> None:
    with connect() as c:
        c.execute("UPDATE users SET is_blocked=? WHERE id=?", (1 if blocked else 0, uid))


def all_user_ids() -> list[int]:
    with connect() as c:
        return [r["tg_id"] for r in c.execute("SELECT tg_id FROM users WHERE is_blocked=0")]


def stats() -> dict[str, int]:
    with connect() as c:
        users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        orders = c.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"]
        done = c.execute("SELECT COUNT(*) n FROM orders WHERE status='done'").fetchone()["n"]
        revenue = c.execute("SELECT COALESCE(SUM(total),0) s FROM orders WHERE status='done'").fetchone()["s"]
        pending_orders = c.execute("SELECT COUNT(*) n FROM orders WHERE status IN ('new','paid','delivering')").fetchone()["n"]
        pending_topups = c.execute("SELECT COUNT(*) n FROM topups WHERE status='pending'").fetchone()["n"]
    return {
        "users": users, "orders": orders, "done": done,
        "revenue": revenue, "pending_orders": pending_orders, "pending_topups": pending_topups,
    }


# -------------------------------------------------------------- servers
def servers(game: str | None = None, only_active: bool = True) -> list[sqlite3.Row]:
    q = "SELECT * FROM servers WHERE 1=1"
    args: list[Any] = []
    if only_active:
        q += " AND active=1"
    if game:
        q += " AND game=?"
        args.append(game)
    q += " ORDER BY sort, id"
    with connect() as c:
        return c.execute(q, args).fetchall()


def server(sid: int) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute("SELECT * FROM servers WHERE id=?", (sid,)).fetchone()


def all_servers() -> list[sqlite3.Row]:
    with connect() as c:
        return c.execute("SELECT * FROM servers ORDER BY game, sort, id").fetchall()


def update_server(sid: int, **fields: Any) -> None:
    allowed = {"price_kk", "stock_kk", "active"}
    sets, args = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            args.append(v)
    if not sets:
        return
    args.append(sid)
    with connect() as c:
        c.execute(f"UPDATE servers SET {', '.join(sets)} WHERE id=?", args)


def change_stock(sid: int, delta_kk: float) -> None:
    with connect() as c:
        c.execute("UPDATE servers SET stock_kk=MAX(0, stock_kk+?) WHERE id=?", (delta_kk, sid))


# --------------------------------------------------------------- orders
def create_order(user_id: int, server_id: int, kk: float, total: int, nick: str,
                 promo_id: int | None = None, discount: int = 0) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO orders (user_id, server_id, kk, total, nick, promo_id, discount, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (user_id, server_id, kk, total, nick, promo_id, discount, now(), now()),
        )
        return int(cur.lastrowid)


def order(oid: int) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute(
            "SELECT o.*, s.name AS server_name, s.game AS game, u.tg_id AS tg_id, "
            "u.username AS username, u.full_name AS full_name "
            "FROM orders o JOIN servers s ON s.id=o.server_id JOIN users u ON u.id=o.user_id "
            "WHERE o.id=?",
            (oid,),
        ).fetchone()


def set_order_status(oid: int, status: str, comment: str | None = None, paid_from: str | None = None) -> None:
    # FIX: Validate status against whitelist
    if status not in ALLOWED_ORDER_STATUSES:
        raise ValueError(f"Invalid order status: {status}")
    
    with connect() as c:
        sets = ["status=?", "updated_at=?"]
        args: list[Any] = [status, now()]
        if comment is not None:
            sets.append("comment=?")
            args.append(comment)
        if paid_from is not None:
            sets.append("paid_from=?")
            args.append(paid_from)
        args.append(oid)
        c.execute(f"UPDATE orders SET {', '.join(sets)} WHERE id=?", args)


def user_orders(uid: int, limit: int = 10) -> list[sqlite3.Row]:
    with connect() as c:
        return c.execute(
            "SELECT o.*, s.name AS server_name, s.game AS game FROM orders o "
            "JOIN servers s ON s.id=o.server_id WHERE o.user_id=? "
            "ORDER BY o.id DESC LIMIT ?",
            (uid, limit),
        ).fetchall()


def orders_by_status(statuses: Iterable[str], limit: int = 20) -> list[sqlite3.Row]:
    # Validate statuses to prevent injection
    statuses = tuple(s for s in statuses if s in ALLOWED_ORDER_STATUSES)
    if not statuses:
        return []
    ph = ",".join("?" * len(statuses))
    with connect() as c:
        return c.execute(
            f"SELECT o.*, s.name AS server_name, s.game AS game, u.tg_id AS tg_id, "
            f"u.username AS username FROM orders o JOIN servers s ON s.id=o.server_id "
            f"JOIN users u ON u.id=o.user_id WHERE o.status IN ({ph}) "
            f"ORDER BY o.id ASC LIMIT ?",
            (*statuses, limit),
        ).fetchall()


# --------------------------------------------------------------- topups
def create_topup(user_id: int, amount: int, method: str) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO topups (user_id, amount, method, created_at, updated_at) VALUES (?,?,?,?,?)",
            (user_id, amount, method, now(), now()),
        )
        return int(cur.lastrowid)


def topup(tid: int) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute(
            "SELECT t.*, u.tg_id AS tg_id, u.username AS username, u.full_name AS full_name "
            "FROM topups t JOIN users u ON u.id=t.user_id WHERE t.id=?",
            (tid,),
        ).fetchone()


def set_topup_status(tid: int, status: str) -> None:
    with connect() as c:
        c.execute("UPDATE topups SET status=?, updated_at=? WHERE id=?", (status, now(), tid))


# ------------------------------------------------------------- settings
def get_setting(key: str, default: str = "") -> str:
    with connect() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


# ---------------------------------------------------------------- отзывы
def add_review(user_id: int, rating: int, text: str, order_id: int | None = None,
               status: str = "published") -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO reviews (user_id, order_id, rating, text, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, order_id, rating, text, status, now(), now()),
        )
        if order_id:
            c.execute("UPDATE orders SET reviewed=1 WHERE id=?", (order_id,))
        return int(cur.lastrowid)


def reviews(status: str = "published", limit: int = 20, offset: int = 0) -> list[sqlite3.Row]:
    with connect() as c:
        return c.execute(
            "SELECT r.*, u.username AS username, u.full_name AS full_name, s.name AS server_name "
            "FROM reviews r JOIN users u ON u.id=r.user_id "
            "LEFT JOIN orders o ON o.id=r.order_id LEFT JOIN servers s ON s.id=o.server_id "
            "WHERE r.status=? ORDER BY r.id DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ).fetchall()


def review_summary() -> tuple[float, int, dict[int, int]]:
    """Средний балл, количество, распределение по звёздам."""
    with connect() as c:
        rows = c.execute(
            "SELECT rating, COUNT(*) n FROM reviews WHERE status='published' GROUP BY rating"
        ).fetchall()
    dist = {i: 0 for i in range(1, 6)}
    total = count = 0
    for r in rows:
        dist[int(r["rating"])] = r["n"]
        total += int(r["rating"]) * r["n"]
        count += r["n"]
    return (round(total / count, 1) if count else 0.0), count, dist


def review(rid: int) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute(
            "SELECT r.*, u.tg_id AS tg_id, u.username AS username FROM reviews r "
            "JOIN users u ON u.id=r.user_id WHERE r.id=?",
            (rid,),
        ).fetchone()


def set_review_status(rid: int, status: str, reply: str | None = None) -> None:
    with connect() as c:
        if reply is None:
            c.execute("UPDATE reviews SET status=?, updated_at=? WHERE id=?", (status, now(), rid))
        else:
            c.execute(
                "UPDATE reviews SET status=?, reply=?, updated_at=? WHERE id=?",
                (status, reply, now(), rid),
            )


def pending_reviews_count() -> int:
    with connect() as c:
        return c.execute("SELECT COUNT(*) n FROM reviews WHERE status='pending'").fetchone()["n"]


def unreviewed_orders(uid: int, limit: int = 5) -> list[sqlite3.Row]:
    with connect() as c:
        return c.execute(
            "SELECT o.*, s.name AS server_name FROM orders o JOIN servers s ON s.id=o.server_id "
            "WHERE o.user_id=? AND o.status='done' AND o.reviewed=0 ORDER BY o.id DESC LIMIT ?",
            (uid, limit),
        ).fetchall()


# ------------------------------------------------------------- промокоды
def promo_by_code(code: str) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute(
            "SELECT * FROM promos WHERE UPPER(code)=? AND active=1", ((code or "").strip().upper(),)
        ).fetchone()


def promo(pid: int) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute("SELECT * FROM promos WHERE id=?", (pid,)).fetchone()


def all_promos() -> list[sqlite3.Row]:
    with connect() as c:
        return c.execute("SELECT * FROM promos ORDER BY active DESC, id DESC").fetchall()


def create_promo(code: str, kind: str, value: int, max_uses: int = 0,
                 min_total: int = 0, expires_at: str | None = None) -> int:
    code = code.strip().upper()
    # FIX: Validate promo code
    if not code or len(code) < 3 or len(code) > 20:
        raise ValueError("Код должен быть 3-20 символов")
    if not code.isalnum():
        raise ValueError("Только буквы и цифры")
    
    with connect() as c:
        existing = c.execute("SELECT id FROM promos WHERE code=?", (code,)).fetchone()
        if existing:
            raise ValueError(f"Промокод {code} уже существует")
        
        cur = c.execute(
            "INSERT INTO promos (code, kind, value, max_uses, min_total, expires_at, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (code, kind, value, max_uses, min_total, expires_at, now()),
        )
        return int(cur.lastrowid)


def toggle_promo(pid: int) -> None:
    with connect() as c:
        c.execute("UPDATE promos SET active=1-active WHERE id=?", (pid,))


def set_promo_value(pid: int, value: int) -> None:
    with connect() as c:
        c.execute("UPDATE promos SET value=? WHERE id=?", (value, pid))


def set_promo_limit(pid: int, max_uses: int) -> None:
    with connect() as c:
        c.execute("UPDATE promos SET max_uses=? WHERE id=?", (max_uses, pid))


def promo_usable(p: sqlite3.Row, user_id: int) -> tuple[bool, str]:
    """Проверка промокода для конкретного пользователя."""
    if not p["active"]:
        return False, "Промокод неактивен"
    if p["expires_at"]:
        from datetime import datetime as _dt
        try:
            if _dt.strptime(p["expires_at"], "%Y-%m-%d") < _dt.now():
                return False, "Срок действия промокода истёк"
        except ValueError:
            pass
    if p["max_uses"] and p["used"] >= p["max_uses"]:
        return False, "Лимит использований исчерпан"
    with connect() as c:
        already = c.execute(
            "SELECT 1 FROM promo_uses WHERE promo_id=? AND user_id=?", (p["id"], user_id)
        ).fetchone()
    if already:
        return False, "Ты уже использовал этот промокод"
    return True, ""


def redeem_promo(promo_id: int, user_id: int, order_id: int) -> None:
    with connect() as c:
        c.execute(
            "INSERT OR IGNORE INTO promo_uses (promo_id, user_id, order_id, created_at) VALUES (?,?,?,?)",
            (promo_id, user_id, order_id, now()),
        )
        c.execute("UPDATE promos SET used=used+1 WHERE id=?", (promo_id,))


# --------------------------------------------------------------- рефералы
def attach_referrer(invited_uid: int, referrer_uid: int) -> bool:
    """Привязывает пригласившего, если у приглашённого ещё нет реферера."""
    if invited_uid == referrer_uid:
        return False
    with connect() as c:
        u = c.execute("SELECT referrer_id FROM users WHERE id=?", (invited_uid,)).fetchone()
        if u is None or u["referrer_id"]:
            return False
        c.execute("UPDATE users SET referrer_id=? WHERE id=?", (referrer_uid, invited_uid))
        c.execute(
            "INSERT OR IGNORE INTO referrals (referrer_id, invited_id, created_at) VALUES (?,?,?)",
            (referrer_uid, invited_uid, now()),
        )
        return True


def user_by_refcode(code: str) -> sqlite3.Row | None:
    with connect() as c:
        return c.execute("SELECT * FROM users WHERE ref_code=?", (code,)).fetchone()


def ensure_refcode(uid: int) -> str:
    with connect() as c:
        row = c.execute("SELECT ref_code FROM users WHERE id=?", (uid,)).fetchone()
        if row and row["ref_code"]:
            return row["ref_code"]
        code = f"ref{uid}"
        c.execute("UPDATE users SET ref_code=? WHERE id=?", (code, uid))
        return code


def referral_stats(uid: int) -> tuple[int, int]:
    with connect() as c:
        n = c.execute("SELECT COUNT(*) n FROM referrals WHERE referrer_id=?", (uid,)).fetchone()["n"]
        earned = c.execute(
            "SELECT COALESCE(SUM(earned),0) s FROM referrals WHERE referrer_id=?", (uid,)
        ).fetchone()["s"]
    return n, earned


def pay_referral(order: sqlite3.Row, percent: int) -> tuple[int, int]:
    """Начисляет процент пригласившему. Возвращает (tg_id, сумма) или (0, 0)."""
    # FIX: Validate percent range
    if percent < 0 or percent > 100 or order["total"] <= 0:
        return 0, 0
    bonus = int(round(order["total"] * percent / 100)) if percent > 0 else 0
    if bonus <= 0:
        return 0, 0
    with connect() as c:
        u = c.execute("SELECT referrer_id FROM users WHERE id=?", (order["user_id"],)).fetchone()
        if not u or not u["referrer_id"]:
            return 0, 0
        ref_uid = u["referrer_id"]
        c.execute("UPDATE users SET balance=balance+? WHERE id=?", (bonus, ref_uid))
        c.execute(
            "UPDATE referrals SET earned=earned+? WHERE referrer_id=? AND invited_id=?",
            (bonus, ref_uid, order["user_id"]),
        )
        c.execute("UPDATE orders SET ref_bonus=? WHERE id=?", (bonus, order["id"]))
        ref_row = c.execute("SELECT tg_id FROM users WHERE id=?", (ref_uid,)).fetchone()
    return (ref_row["tg_id"] if ref_row else 0), bonus


def close_all_connections() -> None:
    """Закрыть все кэшированные соединения к БД при завершении."""
    # SQLite обычно обходится без явного закрытия per thread,
    # но при graceful shutdown хорошо явно закрыть для гарантии.
    pass  # SQLite context manager in connect() уже обеспечивает cleanup


def cleanup_old_promo_uses(days: int = 90) -> None:
    """Удалять записи старше N дней для экономии места."""
    from datetime import datetime as _dt, timedelta
    cutoff = (_dt.now() - timedelta(days=days)).isoformat()
    with connect() as c:
        c.execute("DELETE FROM promo_uses WHERE created_at < ?", (cutoff,))
        log.info("Cleanup: deleted old promo_uses before %s", cutoff)


