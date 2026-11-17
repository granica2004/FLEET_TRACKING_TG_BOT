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
from typing import Callable, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from src import i18n
from src.config import TERMINALS, get_settings
from src.services import access
from src.services.notify import get_bot, notify_admins

settings = get_settings()

def country_name(code: Optional[str]) -> str:
    return i18n.country("ru", code)


def view_button(trip_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=i18n.t(lang, "btn_open_trip"), callback_data=f"v:t:{trip_id}"),
    ]])


async def notify_watchers(session, trip, build: Callable[[str], str]):
    """Отправить событие клиентам и брокерам рейса, каждому на его языке. build(lang) -> текст."""
    bot = get_bot()
    if not bot:
        return
    for p in await access.watchers(session, trip):
        lang = await i18n.get_lang(p.telegram_id)
        try:
            await bot.send_message(p.telegram_id, build(lang), reply_markup=view_button(trip.id, lang),
                                   parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e:
            logger.warning(f"Cannot notify watcher {p.telegram_id}: {e}")


def trip_title(trip, lang: str = "ru") -> str:
    return f"{escape(trip.truck_number)} → {escape(i18n.terminal_short(lang, trip.terminal_code))}"


def _admin_trip_kb(trip_id: int, extra: Optional[list] = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🚛 Открыть рейс", callback_data=f"adm:trip:{trip_id}")]]
    if extra:
        rows.insert(0, extra)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def on_trip_started(session, trip):
    """Рейс стал виден участникам: привязан к сделке или к нему подключился водитель."""
    await notify_watchers(session, trip, lambda lang: i18n.t(lang, "ev_started", title=trip_title(trip, lang)))


async def on_location(session, trip, location, prev_location):
    """Проверить события по новой точке. Вызывается после сохранения точки."""
    if not trip:
        return
    # Пересечение границы
    new_c = (location.country_code or "").lower()
    old_c = (prev_location.country_code or "").lower() if prev_location else ""
    if new_c and old_c and new_c != old_c:
        key = "ev_border_ru" if new_c == "ru" else "ev_border"

        def build(lang):
            return i18n.t(lang, key, a=i18n.country(lang, old_c), b=i18n.country(lang, new_c),
                          title=trip_title(trip, lang), addr=escape(location.address or ""))
        await notify_watchers(session, trip, build)
        await notify_admins("border", build("ru"), _admin_trip_kb(trip.id))

    # Машина у терминала
    t = TERMINALS.get(str(trip.terminal_code or ""), {})
    if t.get("lat") and t.get("lon") and not trip.arrived_notified_at:
        from src.services.geocoder import MapsService
        dist = MapsService.haversine_distance(location.latitude, location.longitude, t["lat"], t["lon"])
        if dist <= settings.arrival_radius_km:
            trip.arrived_notified_at = datetime.utcnow()

            def build_arr(lang):
                return i18n.t(lang, "ev_arrived", title=trip_title(trip, lang),
                              addr=escape(i18n.terminal_address(lang, trip.terminal_code)))
            await notify_watchers(session, trip, build_arr)
            extra = None
            if trip.bitrix_deal_id:
                extra = [InlineKeyboardButton(text="✅ Перевести сделку в «Прибыл»",
                                              callback_data=f"adm:arr:{trip.id}")]
            await notify_admins("arrival", build_arr("ru"), _admin_trip_kb(trip.id, extra))


async def on_last_call(session, trip, km: Optional[int] = None, days: Optional[int] = None):
    if km is not None:
        await notify_watchers(session, trip, lambda lang: i18n.t(lang, "ev_soon_km", title=trip_title(trip, lang), km=km))
    else:
        await notify_watchers(session, trip,
                              lambda lang: i18n.t(lang, "ev_soon_days", title=trip_title(trip, lang), days=days))


async def on_finished(session, trip):
    await notify_watchers(session, trip, lambda lang: i18n.t(lang, "ev_done", title=trip_title(trip, lang)))
