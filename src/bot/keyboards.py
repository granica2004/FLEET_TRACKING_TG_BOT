"""
Клавиатуры для Telegram бота (на языке пользователя; админские — на русском).
"""

from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)

from src.i18n import LANG_NAMES, LANGS, V, t


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANG_NAMES[code], callback_data=f"lang:{code}")] for code in LANGS
    ])


def consent_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_consent"))]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def location_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Основная клавиатура водителя"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_send_location"), request_location=True)],
            [KeyboardButton(text=t(lang, "btn_terminal")), KeyboardButton(text=t(lang, "btn_arrival_date"))],
            [KeyboardButton(text=t(lang, "btn_new_trip")), KeyboardButton(text=t(lang, "btn_finish"))],
        ],
        resize_keyboard=True,
    )


def waiting_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Водитель ждёт привязки к заказу"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_send_location"), request_location=True)],
            [KeyboardButton(text=t(lang, "btn_refresh_status"))],
        ],
        resize_keyboard=True,
    )


def arrival_date_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "arr_today"), callback_data="arrival_today"),
         InlineKeyboardButton(text=t(lang, "arr_tomorrow"), callback_data="arrival_tomorrow")],
        [InlineKeyboardButton(text=t(lang, "arr_2d"), callback_data="arrival_2days"),
         InlineKeyboardButton(text=t(lang, "arr_3d"), callback_data="arrival_3days")],
        [InlineKeyboardButton(text=t(lang, "arr_custom"), callback_data="arrival_custom")],
    ])


def confirm_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_yes"), callback_data="confirm_yes"),
        InlineKeyboardButton(text=t(lang, "btn_no"), callback_data="confirm_no"),
    ]])


def start_trip_keyboard(deal_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_start_tracking"), callback_data=f"start_trip_{deal_id}")],
        [InlineKeyboardButton(text=t(lang, "btn_decline"), callback_data="decline_trip")],
    ])


def cancel_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_cancel"))]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# Тексты кнопок водителя на всех языках (+ старые подписи у водителей с прежней клавиатурой)
TERMINAL_BUTTON_TEXTS = V("btn_terminal") | {"🏭 Адрес терминала назначения"}
ARRIVAL_BUTTON_TEXTS = V("btn_arrival_date") | {"📝 Уведомить о прибытии"}


def role_choice_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_role_driver"))],
            [KeyboardButton(text=t(lang, "btn_role_client"))],
            [KeyboardButton(text=t(lang, "btn_role_broker"))],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


def phone_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_share_phone"), request_contact=True)],
            [KeyboardButton(text=t(lang, "btn_cancel"))],
        ],
        resize_keyboard=True, one_time_keyboard=True,
    )


def skip_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_skip"))], [KeyboardButton(text=t(lang, "btn_cancel"))]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def client_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_my_deals")), KeyboardButton(text=t(lang, "btn_my_trips"))],
                  [KeyboardButton(text=t(lang, "btn_write_dispatcher"))]],
        resize_keyboard=True,
    )


def broker_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_my_trips")), KeyboardButton(text=t(lang, "btn_create_trip"))],
            [KeyboardButton(text=t(lang, "btn_my_deals")), KeyboardButton(text=t(lang, "btn_write_dispatcher"))],
        ],
        resize_keyboard=True,
    )


def admin_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Меню админа — на русском"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Админка"), KeyboardButton(text="📦 Все рейсы")],
            [KeyboardButton(text="➕ Новый рейс")],
        ],
        resize_keyboard=True,
    )


def terminal_nav_keyboard(lat: float, lon: float, lang: str = "ru") -> InlineKeyboardMarkup:
    """Маршрут до терминала в навигаторах"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_route_yandex"),
                              url=f"https://yandex.ru/maps/?rtext=~{lat},{lon}&rtt=auto")],
        [InlineKeyboardButton(text=t(lang, "btn_route_google"),
                              url=f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=driving")],
    ])
