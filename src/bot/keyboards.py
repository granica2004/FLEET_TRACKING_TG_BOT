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
            [KeyboardButton(text="📍 Терминал прибытия"), KeyboardButton(text="📝 Дата прибытия")],
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


TERMINAL_BUTTON_TEXTS = ("📍 Терминал прибытия", "🏭 Адрес терминала назначения")
ARRIVAL_BUTTON_TEXTS = ("📝 Дата прибытия", "📝 Уведомить о прибытии")


def role_choice_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚛 Я водитель")],
            [KeyboardButton(text="📦 Я получатель груза")],
            [KeyboardButton(text="🌍 Я отправитель / брокер")],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


def skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустить")], [KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def client_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📦 Мои рейсы")], [KeyboardButton(text="✉️ Написать диспетчеру")]],
        resize_keyboard=True,
    )


def broker_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Мои рейсы"), KeyboardButton(text="➕ Новый рейс")],
            [KeyboardButton(text="✉️ Написать диспетчеру")],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Админка"), KeyboardButton(text="📦 Все рейсы")],
            [KeyboardButton(text="➕ Новый рейс")],
        ],
        resize_keyboard=True,
    )


def terminal_nav_keyboard(lat: float, lon: float, extra: dict = None) -> InlineKeyboardMarkup:
    """Маршрут до терминала в навигаторах"""
    rows = [
        [InlineKeyboardButton(text="🧭 Маршрут в Яндекс Картах",
                              url=f"https://yandex.ru/maps/?rtext=~{lat},{lon}&rtt=auto")],
        [InlineKeyboardButton(text="🧭 Маршрут в Google Maps",
                              url=f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=driving")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
