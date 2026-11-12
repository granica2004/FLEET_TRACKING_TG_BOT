"""
FastAPI эндпоинты для webhooks от Telegram и Битрикс24.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from loguru import logger
from datetime import datetime

from html import escape

from src.config import get_settings, TERMINALS, terminal_name
from src.services.notify import notify_admins
from src.services.trips import apply_deal_to_trip, deal_link
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
    Всегда отвечаем 200: иначе Telegram будет бесконечно повторять «битое» обновление.
    """
    if not _bot or not _dp:
        logger.error("Bot or dispatcher not initialized")
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        data = await request.json()
        update = Update(**data)
        await _dp.feed_update(_bot, update)
    except Exception as e:
        logger.exception(f"Error processing Telegram webhook: {e}")
    return {"ok": True}


# ==================== BITRIX24 WEBHOOK ====================

async def _read_bitrix_payload(request: Request) -> dict:
    """Битрикс шлёт form-urlencoded (data[FIELDS][ID]=…); на всякий случай понимаем и JSON."""
    ctype = request.headers.get("content-type", "")
    if "json" in ctype:
        body = await request.json()
        flat = {}
        fields = (body.get("data") or {}).get("FIELDS") or {}
        if fields.get("ID"):
            flat["data[FIELDS][ID]"] = fields["ID"]
        token = (body.get("auth") or {}).get("application_token")
        if token:
            flat["auth[application_token]"] = token
        if body.get("document_id"):
            flat["document_id[2]"] = body["document_id"][2] if isinstance(body["document_id"], list) else body["document_id"]
        return flat
    form = await request.form()
    return dict(form)


@router.post("/webhook/bitrix24/deal-update")
async def bitrix_deal_update_webhook(request: Request):
    """
    Исходящий вебхук Битрикс24 (событие ONCRMDEALUPDATE).
    - финальная стадия → завершаем рейс, сообщаем водителю и админам;
    - активная сделка → обновляем привязанный рейс или привязываем ожидающую регистрацию.
    """
    try:
        data = await _read_bitrix_payload(request)
        
        if settings.bitrix_app_token:
            if data.get("auth[application_token]") != settings.bitrix_app_token:
                logger.warning("Bitrix24 webhook: wrong application_token")
                return {"status": "ok", "message": "ignored"}
        
        deal_id = data.get("data[FIELDS][ID]") or data.get("document_id[2]")
        if deal_id and str(deal_id).startswith("DEAL_"):
            deal_id = str(deal_id).replace("DEAL_", "")
        
        if not deal_id or not str(deal_id).isdigit():
            logger.warning(f"No deal ID in webhook data: {list(data.keys())}")
            return {"status": "ok", "message": "No deal ID"}
        
        deal_id = int(deal_id)
        logger.info(f"Received Bitrix24 webhook for deal {deal_id}")
        
        deal = await bitrix_client.get_deal(deal_id)
        if not deal or not deal.get("ID"):
            logger.warning(f"Deal {deal_id} not found")
            return {"status": "ok", "message": "Deal not found"}
        
        stage_id = deal.get("STAGE_ID", "") or ""
        truck_number = (
            deal.get(settings.bitrix_field_truck_number) or
            deal.get(settings.bitrix_field_truck_number_alt) or ""
        ).upper().replace(" ", "")
        is_finished = stage_id in settings.bitrix_final_stages or deal.get("CLOSED") == "Y"
        
        from src.bot.admin import trip_button
        
        async with get_session() as session:
            # Рейс, уже привязанный к этой сделке
            trip = await crud.get_active_trip_by_deal(session, deal_id)
            
            if is_finished:
                if not trip and truck_number:
                    trip = await crud.get_active_trip_by_truck(session, truck_number)
                if not trip:
                    return {"status": "ok", "message": "No active trip"}
                
                await crud.complete_trip(session, trip.id)
                driver = await crud.get_driver_by_id(session, trip.driver_id)
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
                    except Exception as e:
                        logger.error(f"Failed to notify driver: {e}")
                await notify_admins(
                    "done",
                    f"🏁 <b>Рейс завершён по стадии сделки</b> {escape(trip.truck_number)}\n"
                    f"📋 {deal_link(deal_id, deal.get('TITLE'))}",
                    trip_button(trip.id),
                )
                return {"status": "ok", "message": "Trip completed"}
            
            if trip:
                # Обновляем данные рейса (терминал, даты, стадия)
                apply_deal_to_trip(trip, deal)
                return {"status": "ok", "message": "Trip updated"}
            
            if not truck_number:
                return {"status": "ok", "message": "No truck number"}
            
            # Водитель, ожидающий сделку с этим номером
            registration = await crud.find_waiting_registration(session, truck_number)
            if registration:
                driver = await crud.get_driver_by_telegram_id(session, registration.telegram_id)
                waiting_trip = await crud.get_active_trip_by_driver(session, driver.id) if driver else None
                
                if waiting_trip and not waiting_trip.bitrix_deal_id:
                    await crud.match_registration_with_deal(session, truck_number, deal_id)
                    apply_deal_to_trip(waiting_trip, deal)
                    await bitrix_client.update_driver_telegram_id(deal_id, registration.telegram_id)
                    await bitrix_client.add_timeline_comment(
                        deal_id, f"🚛 Водитель {truck_number} привязан к сделке Telegram-ботом отслеживания."
                    )
                    tname = terminal_name(waiting_trip.terminal_code)
                    if _bot:
                        try:
                            await _bot.send_message(
                                registration.telegram_id,
                                f"🎉 <b>Сделка найдена!</b>\n\n"
                                f"📋 {escape(deal.get('TITLE') or 'Без названия')}\n"
                                f"🏭 Терминал: {escape(tname)}\n\n"
                                f"Теперь ваше местоположение будет передаваться брокеру.",
                                reply_markup=keyboards.location_keyboard(),
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify driver about match: {e}")
                    await notify_admins(
                        "match",
                        f"🔗 <b>Рейс привязан к сделке</b> {escape(truck_number)}\n"
                        f"📋 {deal_link(deal_id, deal.get('TITLE'))}\n🏭 {escape(tname)}",
                        trip_button(waiting_trip.id),
                    )
                    return {"status": "ok", "message": "Registration matched"}
            
            # Знакомый водитель без активного рейса — предлагаем начать отслеживание
            if stage_id == settings.bitrix_stage_cargo_sent:
                driver = await crud.get_driver_by_truck_number(session, truck_number)
                if driver and driver.consent_given and driver.is_active:
                    active = await crud.get_active_trip_by_driver(session, driver.id)
                    if not active and _bot:
                        try:
                            await _bot.send_message(
                                driver.telegram_id,
                                f"🚛 <b>Обнаружена новая перевозка!</b>\n\n"
                                f"📋 {escape(deal.get('TITLE') or 'Без названия')}\n"
                                f"🏭 Терминал: {escape(terminal_name(deal.get(settings.bitrix_field_terminal)))}\n\n"
                                f"Начать отслеживание?",
                                reply_markup=keyboards.start_trip_keyboard(deal_id),
                                parse_mode="HTML"
                            )
                            logger.info(f"Sent trip offer to driver {driver.telegram_id}")
                        except Exception as e:
                            logger.error(f"Failed to send trip offer: {e}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.exception(f"Error processing Bitrix24 webhook: {e}")
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
