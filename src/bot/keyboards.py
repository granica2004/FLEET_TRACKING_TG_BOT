"""
Клавиатуры для Telegram бота.
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def consent_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура запроса согласия на геолокацию"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Даю согласие на передачу геолокации")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def location_keyboard() -> ReplyKeyboardMarkup:
    """Основная клавиатура с кнопкой отправки геолокации"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить местоположение", request_location=True)],
            [KeyboardButton(text="📝 Уведомить о прибытии")],
            [KeyboardButton(text="🏭 Адрес терминала назначения")],
            [
                KeyboardButton(text="🔄 Новая перевозка"),
                KeyboardButton(text="❌ Завершить текущую")
            ]
        ],
        resize_keyboard=True
    )


def waiting_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для ожидания сделки (без активного рейса)"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить местоположение", request_location=True)],
            [KeyboardButton(text="🔄 Обновить статус")]
        ],
        resize_keyboard=True
    )


def arrival_date_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура для выбора даты прибытия"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="arrival_today"),
                InlineKeyboardButton(text="Завтра", callback_data="arrival_tomorrow"),
            ],
            [
                InlineKeyboardButton(text="Через 2 дня", callback_data="arrival_2days"),
                InlineKeyboardButton(text="Через 3 дня", callback_data="arrival_3days"),
            ],
            [
                InlineKeyboardButton(text="📅 Указать дату", callback_data="arrival_custom"),
            ]
        ]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no"),
            ]
        ]
    )


def start_trip_keyboard(deal_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для начала отслеживания новой сделки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Начать отслеживание",
                    callback_data=f"start_trip_{deal_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data="decline_trip"
                ),
            ]
        ]
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def remove_keyboard() -> ReplyKeyboardMarkup:
    """Убрать клавиатуру (пустая)"""
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()
