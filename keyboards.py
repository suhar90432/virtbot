"""Клавиатуры для бота."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu() -> ReplyKeyboardMarkup:
    """Главное меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Магазин")],
            [KeyboardButton(text="💰 Баланс")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    """Админ-меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⬅️ Назад")],
        ],
        resize_keyboard=True,
    )


def shop_button(url: str) -> InlineKeyboardMarkup:
    """Кнопка магазина."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Открыть магазин", url=url)],
        ]
    )


def order_status_label(status: str) -> str:
    """Статус заказа на русском."""
    labels = {
        "pending": "⏳ В ожидании",
        "paid": "✅ Оплачено",
        "delivered": "📦 Доставлено",
        "cancelled": "❌ Отменено",
    }
    return labels.get(status, status)
