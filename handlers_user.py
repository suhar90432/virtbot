"""Обработчики для обычных пользователей."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession

import db
from config import CFG

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Главное меню."""
    user = db.ensure_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    text = (
        "🎮 <b>Добро пожаловать в VirtBot!</b>\n\n"
        "💰 Ваш баланс: <b>{}</b> ₽\n\n"
        "Выберите действие:"
    ).format(user.get("balance", 0) if user else 0)
    
    await message.answer(text)


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Меню."""
    text = "📋 <b>Меню:</b>\n\n/start - главное меню\n/app - открыть магазин\n/help - помощь"
    await message.answer(text)


@router.message(Command("app"))
async def cmd_app(message: Message):
    """Открыть магазин (Mini App)."""
    if CFG.webapp_url:
        text = f"🛒 <b>Откройте магазин:</b>\n\n<a href='{CFG.webapp_url}/app'>Перейти в магазин</a>"
    else:
        text = "⚠️ Магазин временно недоступен"
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь."""
    text = (
        "❓ <b>Помощь:</b>\n\n"
        "/start - главное меню\n"
        "/menu - меню\n"
        "/app - открыть магазин\n"
        "/help - помощь\n\n"
        f"Поддержка: {CFG.support}"
    )
    await message.answer(text)
