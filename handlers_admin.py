"""Обработчики для администраторов."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

import db
import keyboards as kb
from config import CFG

router = Router()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель."""
    if message.from_user.id not in CFG.admins:
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        "⚙️ **Админ-панель:**\n\n"
        "Выбери действие:",
        reply_markup=kb.admin_menu()
    )
