"""
Планировщик задач для ежедневного запроса геолокации.
"""

from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
import asyncio

from src.config import get_settings
from src.db.database import get_session
from src.db import crud

settings = get_settings()

# Глобальный планировщик
scheduler = AsyncIOScheduler()

# Placeholder для бота (будет установлен при инициализации)
_bot = None
_keyboards = None


def set_bot_instance(bot, keyboards):
    """Установить экземпляр бота для отправки сообщений"""
    global _bot, _keyboards
    _bot = bot
    _keyboards = keyboards


async def daily_location_request():
    """
    Ежедневный запрос локации у всех активных водителей.
    Запускается по расписанию (например, в 8:00 МСК).
    """
    if not _bot:
        logger.error("Bot instance not set for scheduler")
        return
    
    logger.info("Starting daily location request job")
    
    async with get_session() as session:
        # Получаем всех активных водителей
        drivers = await crud.get_active_drivers(session)
        
        if not drivers:
            logger.info("No active drivers to request location from")
            return
        
        logger.info(f"Requesting location from {len(drivers)} drivers")
        
        for driver in drivers:
            try:
                # Проверяем, есть ли активный рейс
                trip = await crud.get_active_trip_by_driver(session, driver.id)
                
                if trip:
                    # Есть активный рейс — запрашиваем локацию
                    await _bot.send_message(
                        driver.telegram_id,
                        "🌅 Доброе утро!\n\n"
                        "Пожалуйста, отправьте ваше текущее местоположение для обновления статуса перевозки.",
                        reply_markup=_keyboards.location_keyboard()
                    )
                    logger.info(f"Sent location request to driver {driver.telegram_id}")
                else:
                    # Нет активного рейса — просто напоминание
                    logger.debug(f"Driver {driver.telegram_id} has no active trip, skipping")
                
                # Задержка для защиты от rate limit Telegram
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to send to driver {driver.telegram_id}: {e}")
                continue
    
    logger.info("Daily location request job completed")


async def check_trips_and_update_days():
    """
    Ежедневное обновление количества дней в пути для активных рейсов.
    """
    logger.info("Starting daily trips update job")
    
    async with get_session() as session:
        trips = await crud.get_trips_for_daily_check(session)
        
        for trip in trips:
            if trip.shipment_date:
                days = (datetime.utcnow() - trip.shipment_date).days
                if days == trip.days_in_transit:
                    continue
                trip.days_in_transit = days
                
                # Обновляем в Битрикс24 если есть связь со сделкой
                if trip.bitrix_deal_id:
                    from src.services.bitrix import bitrix_client
                    await bitrix_client.update_days_in_transit(trip.bitrix_deal_id, days)
        
        await session.commit()
    
    logger.info("Daily trips update job completed")


async def check_last_call_triggers():
    """
    Проверка триггеров Last Call для активных рейсов.
    """
    logger.info("Starting last call check job")
    
    if not _bot or not _keyboards:
        logger.error("Bot instance not set for scheduler")
        return
    
    from src.services.geocoder import maps_service
    
    async with get_session() as session:
        trips = await crud.get_trips_for_daily_check(session)
        
        for trip in trips:
            if trip.last_call_triggered:
                continue  # Уже сработал
            
            should_trigger = False
            trigger_reason = ""
            
            # Триггер по дням в пути
            if trip.days_in_transit and trip.days_in_transit >= settings.last_call_days_in_transit:
                if not trip.planned_arrival_date:
                    should_trigger = True
                    trigger_reason = f"в пути уже {trip.days_in_transit} дней"
            
            # Триггер по расстоянию (если есть последняя локация)
            if not should_trigger and trip.terminal_code:
                last_location = await crud.get_last_trip_location(session, trip)
                if last_location:
                    route_info = await maps_service.get_distance_to_terminal(
                        last_location.latitude,
                        last_location.longitude,
                        trip.terminal_code
                    )
                    if route_info and route_info["distance_km"] < settings.last_call_distance_km:
                        should_trigger = True
                        trigger_reason = f"до терминала менее {settings.last_call_distance_km} км"
            
            if should_trigger:
                try:
                    # Получаем водителя
                    driver = await crud.get_driver_by_id(session, trip.driver_id) if trip.driver_id else None
                    if driver:
                        await _bot.send_message(
                            driver.telegram_id,
                            f"🏁 Внимание!\n\n"
                            f"Груз {trigger_reason}.\n\n"
                            f"Пожалуйста, укажите планируемую дату прибытия на терминал:",
                            reply_markup=_keyboards.arrival_date_keyboard()
                        )
                        
                        trip.last_call_triggered = True
                        trip.last_call_date = datetime.utcnow()
                        
                        logger.info(f"Last call triggered for trip {trip.id}: {trigger_reason}")
                        
                        from src.services import events
                        await events.on_last_call(session, trip, trigger_reason)
                        from src.services.notify import notify_admins
                        from src.services.trips import deal_link
                        from src.bot.admin import trip_button
                        await notify_admins(
                            "lastcall",
                            f"🏁 <b>Last call</b> {trip.truck_number}: {trigger_reason}\n"
                            f"📋 {deal_link(trip.bitrix_deal_id, trip.bitrix_deal_title)}",
                            trip_button(trip.id),
                        )
                
                except Exception as e:
                    logger.error(f"Failed to send last call to trip {trip.id}: {e}")
        
        await session.commit()
    
    logger.info("Last call check job completed")


async def check_silent_drivers():
    """Сообщить админам о рейсах без геопозиции дольше SILENCE_HOURS (один раз за период молчания)."""
    from datetime import timedelta
    from src.services.notify import notify_admins
    from src.services.trips import ago, deal_link
    from src.bot.admin import trip_button
    
    border = datetime.utcnow() - timedelta(hours=settings.silence_hours)
    async with get_session() as session:
        for trip in await crud.list_active_trips(session):
            if not trip.driver_id:
                continue  # водитель ещё не подключился по ссылке
            loc = await crud.get_last_trip_location(session, trip)
            last_seen = loc.recorded_at if loc else trip.started_at
            if not last_seen or last_seen > border:
                continue
            if trip.silence_alert_at and trip.silence_alert_at > last_seen:
                continue  # уже сообщали за этот период молчания
            trip.silence_alert_at = datetime.utcnow()
            await notify_admins(
                "silence",
                f"🔕 <b>Водитель молчит</b> {trip.truck_number}: последняя точка {ago(loc.recorded_at) if loc else 'не было ни одной'}\n"
                f"📋 {deal_link(trip.bitrix_deal_id, trip.bitrix_deal_title)}",
                trip_button(trip.id),
            )


async def admin_daily_digest():
    """Утренняя сводка админам."""
    from src.services.notify import notify_admins
    from src.bot.admin import _summary_text
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    async with get_session() as session:
        if not await crud.list_active_trips(session):
            return
        text = await _summary_text(session)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛠 Открыть админку", callback_data="adm:menu")]])
    await notify_admins("digest", "☀️ " + text, kb)


def start_scheduler():
    """Запустить планировщик"""
    
    # Ежедневный запрос локации (8:00 МСК = 5:00 UTC)
    scheduler.add_job(
        daily_location_request,
        CronTrigger(
            hour=settings.daily_location_request_hour,
            minute=settings.daily_location_request_minute,
            timezone="UTC"
        ),
        id="daily_location_request",
        replace_existing=True,
        name="Daily location request"
    )
    
    # Обновление дней в пути (каждый день в 0:30 UTC)
    scheduler.add_job(
        check_trips_and_update_days,
        CronTrigger(hour=0, minute=30, timezone="UTC"),
        id="daily_trips_update",
        replace_existing=True,
        name="Daily trips update"
    )
    
    # Проверка Last Call триггеров (каждые 4 часа)
    scheduler.add_job(
        check_last_call_triggers,
        CronTrigger(hour="*/4", minute=0, timezone="UTC"),
        id="last_call_check",
        replace_existing=True,
        name="Last call triggers check"
    )
    
    # Молчащие водители (каждый час)
    scheduler.add_job(
        check_silent_drivers,
        CronTrigger(minute=15, timezone="UTC"),
        id="silent_drivers_check",
        replace_existing=True,
        name="Silent drivers check"
    )
    
    # Утренняя сводка админам
    scheduler.add_job(
        admin_daily_digest,
        CronTrigger(hour=settings.admin_digest_hour, minute=5, timezone="UTC"),
        id="admin_daily_digest",
        replace_existing=True,
        name="Admin daily digest"
    )
    
    scheduler.start()
    logger.info("Scheduler started with jobs: daily_location_request, daily_trips_update, last_call_check, silent_drivers_check, admin_daily_digest")


def stop_scheduler():
    """Остановить планировщик"""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
