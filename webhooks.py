"""
FastAPI эндпоинты для webhooks от Telegram и Битрикс24.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from loguru import logger
from datetime import datetime

from src.config import get_settings, TERMINALS
from src.db.database import get_session
from src.db import crud
from src.services.bitrix import bitrix_client
from src.bot import keyboards

settings = get_settings()
router = APIRouter()

# Placeholder для бота (будет установлен при инициализации)
_bot: Bot = None
_dp: Dispatcher = None


def set_bot_and_dispatcher(bot: Bot, dp: Dispatcher):
    """Установить экземпляры бота и диспетчера"""
    global _bot, _dp
    _bot = bot
    _dp = dp


def get_terminal_display_name(terminal_code: str) -> str:
    """Получить отображаемое название терминала"""
    terminal = TERMINALS.get(terminal_code, {})
    return terminal.get("name_ru") or terminal.get("code") or terminal_code or "Не указан"


# ==================== HEALTH CHECK ====================

@router.get("/health")
async def health_check():
    """Проверка работоспособности сервиса"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "driver-tracking-bot"
    }


# ==================== TELEGRAM WEBHOOK ====================

@router.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    Webhook для получения обновлений от Telegram.
    Используется в production (вместо long polling).
    """
    if not _bot or not _dp:
        logger.error("Bot or dispatcher not initialized")
        raise HTTPException(status_code=500, detail="Bot not initialized")
    
    try:
        data = await request.json()
        update = Update(**data)
        await _dp.feed_update(_bot, update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== BITRIX24 WEBHOOK ====================

@router.post("/webhook/bitrix24/deal-update")
async def bitrix_deal_update_webhook(request: Request):
    """
    Webhook для обновлений сделок из Битрикс24.
    Вызывается при изменении стадии сделки или других полей.
    
    Настройка в Битрикс24:
    CRM → Настройки → Автоматизация → Роботы и триггеры
    Добавить Webhook на событие "Изменение сделки"
    """
    try:
        data = await request.form()
        data = dict(data)
        
        # Извлекаем ID сделки
        deal_id = data.get("data[FIELDS][ID]") or data.get("document_id[2]")
        
        if not deal_id:
            logger.warning(f"No deal ID in webhook data: {data}")
            return {"status": "ok", "message": "No deal ID"}
        
        deal_id = int(deal_id)
        logger.info(f"Received Bitrix24 webhook for deal {deal_id}")
        
        # Получаем полные данные сделки
        deal = await bitrix_client.get_deal(deal_id)
        if not deal:
            logger.warning(f"Deal {deal_id} not found")
            return {"status": "ok", "message": "Deal not found"}
        
        stage_id = deal.get("STAGE_ID", "")
        truck_number = (
            deal.get(settings.bitrix_field_truck_number_alt) or
            deal.get(settings.bitrix_field_truck_number, "")
        )
        
        if not truck_number:
            logger.debug(f"Deal {deal_id} has no truck number")
            return {"status": "ok", "message": "No truck number"}
        
        async with get_session() as session:
            # Проверяем, завершена ли сделка (груз прибыл)
            is_finished = any(final in stage_id for final in settings.bitrix_final_stages)
            
            if is_finished:
                # Ищем активный рейс и завершаем его
                trip = await crud.get_active_trip_by_truck(session, truck_number)
                
                if trip:
                    await crud.complete_trip(session, trip.id)
                    
                    # Уведомляем водителя
                    driver = await crud.get_driver_by_telegram_id(session, trip.driver_id)
                    if driver and _bot:
                        try:
                            await _bot.send_message(
                                driver.telegram_id,
                                "✅ <b>Перевозка завершена!</b>\n\n"
                                "Груз прибыл на терминал. Отслеживание остановлено.\n\n"
                                "Спасибо за работу! Для новой перевозки нажмите /start",
                                reply_markup=keyboards.remove_keyboard(),
                                parse_mode="HTML"
                            )
                            logger.info(f"Notified driver {driver.telegram_id} about trip completion")
                        except Exception as e:
                            logger.error(f"Failed to notify driver: {e}")
                    
                    return {"status": "ok", "message": "Trip completed"}
            
            else:
                # Сделка активна — проверяем регистрации водителей
                registration = await crud.find_waiting_registration(session, truck_number)
                
                if registration:
                    # Есть водитель, ожидающий эту сделку
                    await crud.match_registration_with_deal(session, truck_number, deal_id)
                    
                    # Получаем водителя и обновляем его рейс
                    driver = await crud.get_driver_by_telegram_id(session, registration.telegram_id)
                    
                    if driver:
                        trip = await crud.get_active_trip_by_driver(session, driver.id)
                        
                        if trip and not trip.bitrix_deal_id:
                            terminal_code = deal.get(settings.bitrix_field_terminal)
                            terminal_info = TERMINALS.get(terminal_code, {})
                            terminal_name = get_terminal_display_name(terminal_code)
                            
                            # Обновляем данные рейса
                            trip.bitrix_deal_id = deal_id
                            trip.bitrix_deal_title = deal.get("TITLE")
                            trip.bitrix_stage_id = stage_id
                            trip.terminal_code = terminal_code
                            trip.destination_address = terminal_info.get("address_ru")
                            trip.destination_lat = terminal_info.get("lat")
                            trip.destination_lon = terminal_info.get("lon")
                            
                            # Записываем Telegram ID в сделку
                            await bitrix_client.update_driver_telegram_id(
                                deal_id,
                                registration.telegram_id
                            )
                            
                            # Уведомляем водителя
                            if _bot:
                                try:
                                    await _bot.send_message(
                                        registration.telegram_id,
                                        f"🎉 <b>Сделка найдена!</b>\n\n"
                                        f"📋 {deal.get('TITLE', 'Без названия')}\n"
                                        f"🏭 Терминал: {terminal_name}\n\n"
                                        f"Теперь ваше местоположение будет передаваться брокеру.",
                                        reply_markup=keyboards.location_keyboard(),
                                        parse_mode="HTML"
                                    )
                                    logger.info(f"Notified driver {registration.telegram_id} about deal match")
                                except Exception as e:
                                    logger.error(f"Failed to notify driver about match: {e}")
                        
                        return {"status": "ok", "message": "Registration matched"}
                
                # Проверяем, есть ли водитель с таким номером машины (без активной регистрации)
                driver = await crud.get_driver_by_truck_number(session, truck_number)
                
                if driver and driver.consent_given:
                    terminal_code = deal.get(settings.bitrix_field_terminal)
                    terminal_name = get_terminal_display_name(terminal_code)
                    
                    # Есть знакомый водитель — предлагаем начать отслеживание
                    if _bot:
                        try:
                            await _bot.send_message(
                                driver.telegram_id,
                                f"🚛 <b>Обнаружена новая перевозка!</b>\n\n"
                                f"📋 {deal.get('TITLE', 'Без названия')}\n"
                                f"🏭 Терминал: {terminal_name}\n\n"
                                f"Начать отслеживание?",
                                reply_markup=keyboards.start_trip_keyboard(deal_id),
                                parse_mode="HTML"
                            )
                            logger.info(f"Sent trip offer to driver {driver.telegram_id}")
                        except Exception as e:
                            logger.error(f"Failed to send trip offer: {e}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing Bitrix24 webhook: {e}")
        # Не возвращаем ошибку, чтобы Битрикс не пытался повторить
        return {"status": "error", "message": str(e)}


# ==================== API ДЛЯ РУЧНОГО УПРАВЛЕНИЯ ====================

@router.get("/api/drivers/{telegram_id}")
async def get_driver_info(telegram_id: int):
    """Получить информацию о водителе"""
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, telegram_id)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        trip = await crud.get_active_trip_by_driver(session, driver.id)
        last_location = await crud.get_last_location(session, driver.id)
        
        return {
            "driver": {
                "telegram_id": driver.telegram_id,
                "username": driver.username,
                "truck_number": driver.truck_number,
                "consent_given": driver.consent_given,
            },
            "active_trip": {
                "id": trip.id if trip else None,
                "bitrix_deal_id": trip.bitrix_deal_id if trip else None,
                "terminal": trip.terminal_code if trip else None,
                "days_in_transit": trip.days_in_transit if trip else None,
            } if trip else None,
            "last_location": {
                "lat": last_location.latitude,
                "lon": last_location.longitude,
                "address": last_location.address,
                "recorded_at": last_location.recorded_at.isoformat(),
            } if last_location else None
        }


@router.post("/api/notify/{telegram_id}")
async def send_notification(telegram_id: int, request: Request):
    """Отправить уведомление водителю"""
    if not _bot:
        raise HTTPException(status_code=500, detail="Bot not initialized")
    
    data = await request.json()
    message = data.get("message", "")
    
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    
    try:
        await _bot.send_message(telegram_id, message, parse_mode="HTML")
        return {"status": "ok", "message": "Notification sent"}
    except Exception as e:
        logger.error(f"Failed to send notification to {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
