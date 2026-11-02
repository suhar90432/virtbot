"""Обработчики для обычных пользователей."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

import db
import keyboards as kb
from config import CFG

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Главное меню."""
    user = db.ensure_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer(
        "🎮 **Добро пожаловать в VirtBot!**\n\n"
        "Выбери действие:",
        reply_markup=kb.main_menu()
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Меню."""
    await message.answer(
        "📋 **Меню:**",
        reply_markup=kb.main_menu()
    )


@router.message(Command("app"))
async def cmd_app(message: Message):
    """Открыть магазин (Mini App)."""
    await message.answer(
        "🛒 **Откройте магазин:**",
        reply_markup=kb.shop_button(CFG.webapp_url)
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь."""
    await message.answer(
        "❓ **Помощь:**\n\n"
        "/start — главное меню\n"
        "/menu — меню\n"
        "/app — открыть магазин\n"
        "/help — помощь\n\n"
        f"Поддержка: {CFG.support}"
    )
