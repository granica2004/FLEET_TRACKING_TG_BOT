"""
Запись в сделку Битрикс24 о подключении водителя к рейсу.

Одинаково для всех путей привязки: водитель нашёлся по номеру, пришёл по ссылке,
диспетчер привязал вручную, заказ появился после регистрации.
Пишет комментарий и сразу отправляет последнюю известную точку — иначе точки,
присланные до привязки, в сделку не попадут.
"""

from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

from src.db import crud
from src.services.bitrix import bitrix_client

# Точку водителя без рейса считаем актуальной, если ей не больше стольких часов
FRESH_HOURS = 48


async def announce_link(session, trip, driver, how: str) -> bool:
    """Комментарий «водитель подключён» + последняя точка в сделку. Возвращает True, если точка отправлена."""
    if not trip or not trip.bitrix_deal_id:
        return False
    deal_id = trip.bitrix_deal_id
    who = "водитель ещё не подключился"
    if driver:
        name = " ".join(x for x in [driver.first_name, driver.last_name] if x) or "без имени"
        who = name + (f" (@{driver.username})" if driver.username else "") + f", Telegram ID {driver.telegram_id}"
    await bitrix_client.add_timeline_comment(
        deal_id,
        f"🚛 <b>Рейс {trip.truck_number} привязан к сделке</b> в Telegram-боте отслеживания: {how}.\n"
        f"Водитель: {who}.",
    )

    # Последняя точка: по рейсу, иначе свежая точка водителя
    loc = await crud.get_last_trip_location(session, trip)
    if not loc and driver:
        last = await crud.get_last_location(session, driver.id)
        if last and last.recorded_at >= datetime.utcnow() - timedelta(hours=FRESH_HOURS):
            loc = last
    if not loc:
        return False
    try:
        ok = await bitrix_client.add_location_comment(
            deal_id, loc.address or f"{loc.latitude:.6f}, {loc.longitude:.6f}",
            loc.latitude, loc.longitude,
            distance_km=loc.distance_to_destination_km, recorded_at=loc.recorded_at,
        )
        if ok:
            if not loc.trip_id:
                loc.trip_id = trip.id
            await crud.mark_location_synced(session, loc.id, deal_id)
        return ok
    except Exception as e:
        logger.error(f"Cannot post last location to deal {deal_id}: {e}")
        return False
