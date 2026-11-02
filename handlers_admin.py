"""Обработчики для администраторов."""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from config import CFG

router = Router()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель."""
    if message.from_user.id not in CFG.admins:
        await message.answer("❌ Доступ запрещён")
        return
    
    text = "⚙️ <b>Админ-панель:</b>\n\nВыбери действие:"
    await message.answer(text)
