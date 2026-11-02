"""Инлайн-клавиатуры. Всё оформление — в зелёной палитре."""
from __future__ import annotations

import sqlite3

from aiogram.types import (InlineKeyboardButton as B, InlineKeyboardMarkup as KB,
                           KeyboardButton, ReplyKeyboardMarkup, WebAppInfo)

from db import ORDER_FLOW
from theme import GREEN, LEAF, MONEY, STAR
from utils import game_emoji, game_title, kk, money

G = "🟢"


def main_menu(is_admin: bool = False, has_review: bool = False) -> KB:
    rows = [
        [B(text="🌿 Купить вирты", callback_data="buy")],
        [B(text=f"💚 Пополнить · {MONEY}", callback_data="topup"), B(text="👤 Профиль", callback_data="profile")],
        [B(text="⭐ Отзывы", callback_data="reviews:0")],
    ]
    if has_review:
        rows.append([B(text="✍️ Оставить отзыв", callback_data="wr:new")])
    rows += [
        [B(text="🧾 Мои заказы", callback_data="my_orders"), B(text="🎁 Бонусы", callback_data="bonus")],
        [B(text="ℹ️ Помощь", callback_data="help")],
    ]
    if is_admin:
        rows.append([B(text="🛠 Админ-панель", callback_data="admin")])
    return KB(inline_keyboard=rows)


def back_menu() -> KB:
    return KB(inline_keyboard=[[B(text="⬅️ В меню", callback_data="menu")]])


def reply_menu(webapp_url: str | None = None) -> ReplyKeyboardMarkup:
    """Постоянная клавиатура снизу; сюда же кнопка Mini App."""
    rows = [[KeyboardButton(text="🌿 Купить вирты"), KeyboardButton(text="💚 Баланс")]]
    if webapp_url:
        rows.append([KeyboardButton(text="📱 Открыть магазин", web_app=WebAppInfo(url=webapp_url))])
    rows.append([KeyboardButton(text="⭐ Отзывы"), KeyboardButton(text="ℹ️ Помощь")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def games_menu(games: dict[str, int]) -> KB:
    rows = [
        [B(text=f"{game_emoji(g)} {game_title(g)}  ·  от {money(min_price)} за 1кк", callback_data=f"game:{g}")]
        for g, min_price in games.items()
    ]
    rows.append([B(text="⭐ Отзывы о нас", callback_data="reviews:0")])
    rows.append([B(text="⬅️ В меню", callback_data="menu")])
    return KB(inline_keyboard=rows)


def servers_menu(game: str, items: list[sqlite3.Row]) -> KB:
    rows = []
    for r in items:
        stock = r["stock_kk"]
        mark = "🟢" if stock >= 50 else ("🟡" if stock > 0 else "🔴")
        rows.append([
            B(text=f"{mark} {r['name']} — {money(r['price_kk'])}/кк", callback_data=f"srv:{r['id']}")
        ])
    rows.append([B(text="⬅️ Назад", callback_data="buy")])
    return KB(inline_keyboard=rows)


def kk_menu(sid: int) -> KB:
    quick = [1, 5, 10, 25, 50, 100]
    rows, row = [], []
    for q in quick:
        row.append(B(text=f"{q}кк", callback_data=f"kk:{sid}:{q}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([B(text="✏️ Своё количество", callback_data=f"kkcustom:{sid}")])
    rows.append([B(text="⬅️ Назад", callback_data="buy")])
    return KB(inline_keyboard=rows)


def confirm_menu(sid: int, amount: float) -> KB:
    return KB(inline_keyboard=[
        [B(text="✅ Подтвердить заказ", callback_data=f"orderok:{sid}:{amount}")],
        [B(text="🎟 У меня промокод", callback_data=f"prompt:{sid}:{amount}")],
        [B(text="⬅️ Изменить количество", callback_data=f"srv:{sid}")],
    ])


def order_pay_menu(oid: int, by_balance: bool) -> KB:
    rows = []
    if by_balance:
        rows.append([B(text=f"💚 Оплатить с баланса", callback_data=f"paybal:{oid}")])
    rows.append([B(text="🏦 Оплатить переводом", callback_data=f"paymanual:{oid}")])
    rows.append([B(text="❌ Отменить заказ", callback_data=f"cancelorder:{oid}")])
    return KB(inline_keyboard=rows)


def topup_menu() -> KB:
    amounts = [500, 1000, 2000, 5000, 10000]
    rows, row = [], []
    for a in amounts:
        row.append(B(text=f"{a} ₽", callback_data=f"tu:{a}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([B(text="✏️ Своя сумма", callback_data="tucustom")])
    rows.append([B(text="⬅️ В меню", callback_data="menu")])
    return KB(inline_keyboard=rows)


def topup_method_menu(amount_rub: int) -> KB:
    return KB(inline_keyboard=[
        [B(text="🏦 СБП / карта", callback_data=f"tum:{amount_rub}:card")],
        [B(text="🪙 USDT", callback_data=f"tum:{amount_rub}:crypto")],
        [B(text="⬅️ Назад", callback_data="topup")],
    ])


# ------------------------------------------------------------------ отзывы
def review_rate_menu() -> KB:
    rows = [
        [B(text="5 ⭐", callback_data="wr:rate:5"), B(text="4 ⭐", callback_data="wr:rate:4"),
         B(text="3 ⭐", callback_data="wr:rate:3")],
        [B(text="2 ⭐", callback_data="wr:rate:2"), B(text="1 ⭐", callback_data="wr:rate:1")],
        [B(text="⬅️ Отмена", callback_data="reviews:0")],
    ]
    return KB(inline_keyboard=rows)


def reviews_menu(page: int, pages: int, can_write: bool = True) -> KB:
    rows = []
    nav = []
    if page > 0:
        nav.append(B(text="◀️", callback_data=f"reviews:{page - 1}"))
    nav.append(B(text=f"{page + 1}/{max(pages, 1)}", callback_data="noop"))
    if page + 1 < pages:
        nav.append(B(text="▶️", callback_data=f"reviews:{page + 1}"))
    if len(nav) > 1:
        rows.append(nav)
    if can_write:
        rows.append([B(text="✍️ Написать отзыв", callback_data="wr:new")])
    rows.append([B(text="⬅️ В меню", callback_data="menu")])
    return KB(inline_keyboard=rows)


def review_order_pick(orders: list[sqlite3.Row]) -> KB:
    rows = [[B(text=f"#{o['id']} · {o['server_name']}", callback_data=f"wr:ord:{o['id']}")] for o in orders]
    rows.append([B(text="Без привязки к заказу", callback_data="wr:ord:0")])
    rows.append([B(text="⬅️ Назад", callback_data="reviews:0")])
    return KB(inline_keyboard=rows)


def review_moderation_menu(rid: int) -> KB:
    return KB(inline_keyboard=[
        [B(text="✅ Опубликовать", callback_data=f"rv:ok:{rid}")],
        [B(text="🗑 Удалить", callback_data=f"rv:del:{rid}")],
        [B(text="💬 Ответить", callback_data=f"rv:rep:{rid}")],
        [B(text="⬅️ К отзывам", callback_data="adm:reviews")],
    ])


def admin_reviews_switch(items: list[sqlite3.Row]) -> KB:
    rows, row = [], []
    for r in items:
        row.append(B(text=f"#{r['id']} {STAR}{r['rating']}", callback_data=f"rv:{r['id']}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([B(text="👁 Все отзывы", callback_data="adm:reviews:all")])
    rows.append([B(text="⬅️ В админку", callback_data="admin")])
    return KB(inline_keyboard=rows)


# ------------------------------------------------------------- промокоды
def promo_admin_menu(promos: list[sqlite3.Row]) -> KB:
    rows = []
    for p in promos:
        icon = "🟢" if p["active"] else "⚪️"
        val = f"{p['value']}%" if p["kind"] == "percent" else money(p["value"])
        rows.append([B(
            text=f"{icon} {p['code']} · {val} · {p['used']}/{p['max_uses'] or '∞'}",
            callback_data=f"pm:{p['id']}",
        )])
    rows.append([B(text="➕ Создать промокод", callback_data="pm:new")])
    rows.append([B(text="⬅️ В админку", callback_data="admin")])
    return KB(inline_keyboard=rows)


def promo_card_menu(pid: int, active: int) -> KB:
    return KB(inline_keyboard=[
        [B(text="💵 Изменить значение", callback_data=f"pmv:{pid}")],
        [B(text="🔢 Изменить лимит", callback_data=f"pml:{pid}")],
        [B(text="⏸ Выключить" if active else "▶️ Включить", callback_data=f"pmt:{pid}")],
        [B(text="⬅️ К промокодам", callback_data="adm:promos")],
    ])


def promo_kind_menu() -> KB:
    return KB(inline_keyboard=[
        [B(text="Процент от суммы", callback_data="pmk:percent")],
        [B(text="Фиксированная скидка", callback_data="pmk:fixed")],
        [B(text="⬅️ Отмена", callback_data="adm:promos")],
    ])


# -------------------------------------------------------------- рефералы
def bonus_menu(has_refs: bool) -> KB:
    rows = [[B(text="🎟 Ввести промокод", callback_data="promouse")]]
    rows.append([B(text="🔗 Моя реф-ссылка", callback_data="ref")])
    rows.append([B(text="⬅️ В меню", callback_data="menu")])
    return KB(inline_keyboard=rows)


def share_ref(ref_link: str, text: str) -> KB:
    from urllib.parse import quote
    share = f"https://t.me/share/url?url={quote(ref_link)}&text={quote(text)}"
    return KB(inline_keyboard=[
        [B(text="📤 Поделиться", url=share)],
        [B(text="⬅️ Назад", callback_data="bonus")],
    ])


# ------------------------------------------------------------------ админ
def admin_menu(pending_orders: int, pending_topups: int, pending_reviews: int = 0) -> KB:
    return KB(inline_keyboard=[
        [B(text=f"📦 Заказы ({pending_orders})", callback_data="adm:orders"),
         B(text=f"💰 Пополнения ({pending_topups})", callback_data="adm:topups")],
        [B(text=f"⭐ Отзывы ({pending_reviews})", callback_data="adm:reviews")],
        [B(text="🎟 Промокоды", callback_data="adm:promos"), B(text="🗂 Товар и цены", callback_data="adm:goods")],
        [B(text="📊 Статистика", callback_data="adm:stats"), B(text="📢 Рассылка", callback_data="adm:broadcast")],
        [B(text="⬅️ В меню", callback_data="menu")],
    ])


def admin_order_menu(oid: int, status: str) -> KB:
    rows = []
    if status == "new":
        rows.append([B(text="✅ Подтвердить оплату", callback_data=f"ao:pay:{oid}")])
    if status in ("paid", "delivering"):
        rows.append([B(text="🚀 Отметить выполненным", callback_data=f"ao:done:{oid}")])
    if status in ("new", "paid", "delivering"):
        rows.append([B(text="↩️ Отменить и вернуть", callback_data=f"ao:cancel:{oid}")])
    rows.append([B(text="⬅️ К списку", callback_data="adm:orders")])
    return KB(inline_keyboard=rows)


def admin_topup_menu(tid: int) -> KB:
    return KB(inline_keyboard=[
        [B(text="✅ Зачислить", callback_data=f"at:ok:{tid}")],
        [B(text="❌ Отклонить", callback_data=f"at:no:{tid}")],
        [B(text="⬅️ К списку", callback_data="adm:topups")],
    ])


def goods_menu(rows_in: list[sqlite3.Row]) -> KB:
    rows = []
    for r in rows_in:
        icon = "🟢" if r["active"] else "⚪️"
        rows.append([B(
            text=f"{icon} {r['name']} — {money(r['price_kk'])} · {kk(r['stock_kk'])}",
            callback_data=f"ag:{r['id']}",
        )])
    rows.append([B(text="⬅️ Назад", callback_data="admin")])
    return KB(inline_keyboard=rows)


def goods_edit_menu(sid: int, active: int) -> KB:
    return KB(inline_keyboard=[
        [B(text="💵 Изменить цену", callback_data=f"agp:{sid}")],
        [B(text="📦 Изменить наличие", callback_data=f"ags:{sid}")],
        [B(text="👁 Скрыть" if active else "👁 Показать", callback_data=f"agt:{sid}")],
        [B(text="⬅️ К товару", callback_data="adm:goods")],
    ])


def broadcast_confirm() -> KB:
    return KB(inline_keyboard=[
        [B(text="🚀 Отправить всем", callback_data="bcastgo")],
        [B(text="❌ Отмена", callback_data="admin")],
    ])


def admin_orders_switch(order_ids: list[int]) -> KB:
    rows, row = [], []
    for oid in order_ids:
        row.append(B(text=f"#{oid}", callback_data=f"aov:{oid}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([B(text="⬅️ В админку", callback_data="admin")])
    return KB(inline_keyboard=rows)


def admin_topups_switch(items: list[tuple[int, int]]) -> KB:
    rows, row = [], []
    for tid, amount in items:
        row.append(B(text=f"#{tid} · {amount // 100}₽", callback_data=f"atv:{tid}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([B(text="⬅️ В админку", callback_data="admin")])
    return KB(inline_keyboard=rows)


def admin_topup_card_menu(tid: int) -> KB:
    return KB(inline_keyboard=[
        [B(text="✅ Зачислить", callback_data=f"at:ok:{tid}")],
        [B(text="❌ Отклонить", callback_data=f"at:no:{tid}")],
        [B(text="⬅️ К списку", callback_data="adm:topups")],
    ])


def order_status_label(status: str) -> str:
    return ORDER_FLOW.get(status, status)
