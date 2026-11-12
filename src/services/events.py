"""
События рейса и рассылка участникам (клиентам и брокерам с доступом).

- пересечение границы (смена страны между точками);
- машина у терминала (в радиусе ARRIVAL_RADIUS_KM от координат терминала);
- рейс привязан / водитель подключился;
- last call (близко к терминалу);
- рейс завершён.
"""

from datetime import datetime
from html import escape
from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from src.config import TERMINALS, get_settings, terminal_name
from src.services import access
from src.services.notify import get_bot, notify_admins

settings = get_settings()

COUNTRIES = {
    "ru": "Россия", "kz": "Казахстан", "uz": "Узбекистан", "tj": "Таджикистан", "kg": "Кыргызстан",
    "tm": "Туркменистан", "ir": "Иран", "az": "Азербайджан", "ge": "Грузия", "am": "Армения",
    "by": "Беларусь", "cn": "Китай", "tr": "Турция", "af": "Афганистан", "mn": "Монголия",
}


def country_name(code: Optional[str]) -> str:
    return COUNTRIES.get((code or "").lower(), (code or "?").upper())


def view_button(trip_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚛 Открыть рейс", callback_data=f"v:t:{trip_id}"),
    ]])


async def notify_watchers(session, trip, text: str):
    """Отправить событие клиентам и брокерам рейса."""
    bot = get_bot()
    if not bot:
        return
    for p in await access.watchers(session, trip):
        try:
            await bot.send_message(p.telegram_id, text, reply_markup=view_button(trip.id),
                                   parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e:
            logger.warning(f"Cannot notify watcher {p.telegram_id}: {e}")


def trip_title(trip) -> str:
    return f"{escape(trip.truck_number)} → {escape(terminal_name(trip.terminal_code).split(' — ')[0])}"


def _admin_trip_kb(trip_id: int, extra: Optional[list] = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🚛 Открыть рейс", callback_data=f"adm:trip:{trip_id}")]]
    if extra:
        rows.insert(0, extra)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def on_trip_started(session, trip):
    """Рейс стал виден участникам: привязан к сделке или к нему подключился водитель."""
    await notify_watchers(
        session, trip,
        f"🚛 <b>Груз в пути</b>: {trip_title(trip)}\n"
        f"Вы можете смотреть местоположение машины и маршрут в этом боте.",
    )


async def on_location(session, trip, location, prev_location):
    """Проверить события по новой точке. Вызывается после сохранения точки."""
    if not trip:
        return
    # Пересечение границы
    new_c = (location.country_code or "").lower()
    old_c = (prev_location.country_code or "").lower() if prev_location else ""
    if new_c and old_c and new_c != old_c:
        text = (f"🛂 <b>Машина пересекла границу</b>: {country_name(old_c)} → {country_name(new_c)}\n"
                f"{trip_title(trip)}\n📍 {escape(location.address or '')}")
        if new_c == "ru":
            text = text.replace("Машина пересекла границу", "Машина въехала в Россию")
        await notify_watchers(session, trip, text)
        await notify_admins("border", text, _admin_trip_kb(trip.id))

    # Машина у терминала
    t = TERMINALS.get(str(trip.terminal_code or ""), {})
    if t.get("lat") and t.get("lon") and not trip.arrived_notified_at:
        from src.services.geocoder import MapsService
        dist = MapsService.haversine_distance(location.latitude, location.longitude, t["lat"], t["lon"])
        if dist <= settings.arrival_radius_km:
            trip.arrived_notified_at = datetime.utcnow()
            text = f"🏁 <b>Машина у терминала</b>: {trip_title(trip)}\n📍 {escape(t.get('address_ru', ''))}"
            await notify_watchers(session, trip, text)
            extra = None
            if trip.bitrix_deal_id:
                extra = [InlineKeyboardButton(text="✅ Перевести сделку в «Прибыл»",
                                              callback_data=f"adm:arr:{trip.id}")]
            await notify_admins("arrival", text, _admin_trip_kb(trip.id, extra))


async def on_last_call(session, trip, reason: str):
    await notify_watchers(session, trip, f"⏳ <b>Скоро прибытие</b>: {trip_title(trip)} — {escape(reason)}")


async def on_finished(session, trip):
    await notify_watchers(session, trip, f"✅ <b>Перевозка завершена</b>: {trip_title(trip)}")
