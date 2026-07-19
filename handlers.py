"""
Обработчики команд и сообщений Telegram бота.
"""

import re
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from loguru import logger

from src.bot.states import RegistrationStates, ArrivalStates
from src.bot import keyboards
from src.db.database import get_session
from src.db import crud
from src.services.bitrix import bitrix_client
from src.services.geocoder import maps_service
from src.config import get_settings, TERMINALS

settings = get_settings()
router = Router()

# Регулярное выражение для российских номеров
# Формат: А123ВС77 или А123ВС777
RU_PLATE_REGEX = r'^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$'

# Расширенный формат для иностранных номеров
FOREIGN_PLATE_REGEX = r'^[A-Z0-9]{2,10}$'


def validate_plate_number(plate: str) -> bool:
    """Проверка формата номера транспортного средства"""
    plate_clean = plate.upper().replace(" ", "").replace("-", "")
    
    # Российский формат
    if re.match(RU_PLATE_REGEX, plate_clean):
        return True
    
    # Иностранный формат (более свободный)
    if re.match(FOREIGN_PLATE_REGEX, plate_clean):
        return True
    
    # Составной номер (тягач/прицеп)
    if "/" in plate_clean:
        parts = plate_clean.split("/")
        return all(len(p) >= 3 for p in parts)
    
    return len(plate_clean) >= 3  # Минимум 3 символа


def get_terminal_display_name(terminal_code: str) -> str:
    """Получить отображаемое название терминала"""
    terminal = TERMINALS.get(terminal_code, {})
    return terminal.get("name_ru") or terminal.get("code") or terminal_code or "Не указан"


# ==================== КОМАНДА /start ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    
    async with get_session() as session:
        # Проверяем, есть ли водитель в базе
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        
        if driver and driver.consent_given:
            # Водитель уже зарегистрирован — проверяем активный рейс
            trip = await crud.get_active_trip_by_driver(session, driver.id)
            
            if trip:
                terminal_name = get_terminal_display_name(trip.terminal_code)
                await message.answer(
                    f"👋 С возвращением!\n\n"
                    f"🚛 Активный рейс: {trip.truck_number}\n"
                    f"🏭 Терминал: {terminal_name}\n\n"
                    f"Отправьте своё местоположение для обновления статуса.",
                    reply_markup=keyboards.location_keyboard()
                )
                await state.set_state(RegistrationStates.active_trip)
            else:
                # Нет активного рейса — предлагаем начать новый
                await message.answer(
                    f"👋 С возвращением, {driver.first_name or 'водитель'}!\n\n"
                    f"Введите номер тягача для начала новой перевозки (без пробелов):",
                    reply_markup=keyboards.cancel_keyboard()
                )
                await state.set_state(RegistrationStates.waiting_truck_number)
        else:
            # Новый пользователь — запрашиваем согласие
            if not driver:
                driver = await crud.create_driver(
                    session,
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name,
                )
            
            await message.answer(
                "🚛 <b>Бот отслеживания перевозок</b>\n\n"
                "Добро пожаловать! Этот бот помогает отслеживать местоположение груза "
                "на пути к таможенному терминалу.\n\n"
                "Для работы необходимо ваше согласие на передачу данных о местоположении. "
                "Данные используются исключительно для мониторинга доставки груза и будут "
                "переданы таможенному брокеру.\n\n"
                "Нажмите кнопку ниже, если согласны:",
                reply_markup=keyboards.consent_keyboard(),
                parse_mode="HTML"
            )
            await state.set_state(RegistrationStates.waiting_consent)


# ==================== СОГЛАСИЕ ====================

@router.message(RegistrationStates.waiting_consent, F.text.contains("согласие"))
async def process_consent(message: Message, state: FSMContext):
    """Обработка согласия на передачу геолокации"""
    
    async with get_session() as session:
        await crud.update_driver_consent(session, message.from_user.id, True)
    
    await message.answer(
        "✅ Согласие получено! Спасибо.\n\n"
        "Теперь введите <b>номер тягача</b> (без пробелов):\n"
        "Например: А123ВС77 или 60144OBA",
        reply_markup=keyboards.cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegistrationStates.waiting_truck_number)


# ==================== НОМЕР ТЯГАЧА ====================

@router.message(RegistrationStates.waiting_truck_number)
async def process_truck_number(message: Message, state: FSMContext):
    """Обработка ввода номера тягача"""
    
    if message.text == "❌ Отмена":
        await message.answer(
            "Регистрация отменена. Для начала нажмите /start",
            reply_markup=keyboards.remove_keyboard()
        )
        await state.clear()
        return
    
    truck = message.text.strip().upper().replace(" ", "").replace("-", "")
    
    if not validate_plate_number(truck):
        await message.answer(
            "❌ Неверный формат номера.\n\n"
            "Введите номер в формате:\n"
            "• Российский: А123ВС77\n"
            "• Иностранный: 60144OBA\n"
            "• Составной: 60144OBA/606739AA"
        )
        return
    
    # Сохраняем номер тягача и сразу переходим к поиску сделки
    # (номер прицепа необязателен)
    await state.update_data(truck_number=truck)
    
    async with get_session() as session:
        # Обновляем данные водителя
        driver = await crud.update_driver_transport(
            session, message.from_user.id, truck, None
        )
        
        # Ищем сделку в Битрикс24 (включая стадию "Новая")
        deal = await bitrix_client.find_deal_by_truck_number(truck)
        
        if deal:
            # Сделка найдена — создаём рейс
            terminal_code = deal.get(settings.bitrix_field_terminal)
            terminal_info = TERMINALS.get(terminal_code, {})
            terminal_name = get_terminal_display_name(terminal_code)
            
            trip = await crud.create_trip(
                session,
                driver_id=driver.id,
                truck_number=truck,
                trailer_number=None,
                bitrix_deal_id=int(deal["ID"]),
                bitrix_deal_title=deal.get("TITLE"),
                bitrix_stage_id=deal.get("STAGE_ID"),
                terminal_code=terminal_code,
                destination_address=terminal_info.get("address_ru"),
                destination_lat=terminal_info.get("lat"),
                destination_lon=terminal_info.get("lon"),
            )
            
            # Записываем Telegram ID водителя в сделку
            await bitrix_client.update_driver_telegram_id(
                int(deal["ID"]),
                message.from_user.id,
                message.from_user.username
            )
            
            await message.answer(
                f"✅ <b>Регистрация завершена!</b>\n\n"
                f"🚛 Тягач: {truck}\n\n"
                f"📋 <b>Найдена сделка:</b>\n"
                f"{deal.get('TITLE', 'Без названия')}\n\n"
                f"🏭 <b>Терминал назначения:</b>\n"
                f"{terminal_name}\n"
                f"{terminal_info.get('address_ru', '')}\n\n"
                f"Нажмите кнопку для отправки текущего местоположения.",
                reply_markup=keyboards.location_keyboard(),
                parse_mode="HTML"
            )
            await state.set_state(RegistrationStates.active_trip)
            
        else:
            # Сделка не найдена — создаём регистрацию для ожидания
            await crud.create_driver_registration(
                session, message.from_user.id, truck, None
            )
            
            # Создаём рейс без привязки к сделке
            trip = await crud.create_trip(
                session,
                driver_id=driver.id,
                truck_number=truck,
                trailer_number=None,
            )
            
            await message.answer(
                f"✅ <b>Регистрация завершена!</b>\n\n"
                f"🚛 Тягач: {truck}\n\n"
                f"⚠️ <b>Активная сделка пока не найдена.</b>\n"
                f"Вы получите уведомление, когда сделка будет создана.\n\n"
                f"Пока можете отправлять своё местоположение:",
                reply_markup=keyboards.waiting_keyboard(),
                parse_mode="HTML"
            )
            await state.set_state(RegistrationStates.active_trip)


# ==================== ГЕОЛОКАЦИЯ ====================

@router.message(RegistrationStates.active_trip, F.location)
async def handle_location(message: Message, state: FSMContext):
    """Обработка полученной геолокации"""
    
    lat = message.location.latitude
    lon = message.location.longitude
    
    logger.info(f"Received location from {message.from_user.id}: {lat}, {lon}")
    
    # Получаем адрес по координатам
    try:
        address = await maps_service.reverse_geocode(lat, lon)
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        address = None
    
    if not address:
        address = f"Координаты: {lat:.6f}, {lon:.6f}"
    
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if not driver:
            await message.answer("❌ Ошибка: водитель не найден. Нажмите /start")
            return
        
        trip = await crud.get_active_trip_by_driver(session, driver.id)
        
        # Рассчитываем расстояние до терминала
        distance_info = None
        if trip and trip.terminal_code:
            try:
                distance_info = await maps_service.get_distance_to_terminal(
                    lat, lon, trip.terminal_code
                )
            except Exception as e:
                logger.error(f"Distance calculation error: {e}")
        
        # Сохраняем локацию
        location = await crud.save_location(
            session,
            driver_id=driver.id,
            latitude=lat,
            longitude=lon,
            address=address,
            trip_id=trip.id if trip else None,
            distance_to_destination=distance_info["distance_km"] if distance_info else None,
        )
        
        # Если есть связь со сделкой — синхронизируем с Битрикс24
        bitrix_synced = False
        if trip and trip.bitrix_deal_id:
            try:
                success = await bitrix_client.add_location_comment(
                    trip.bitrix_deal_id,
                    address,
                    lat, lon,
                    distance_km=distance_info["distance_km"] if distance_info else None,
                    eta=distance_info["eta_text"] if distance_info else None,
                )
                
                if success:
                    await crud.mark_location_synced(session, location.id, trip.bitrix_deal_id)
                    bitrix_synced = True
            except Exception as e:
                logger.error(f"Bitrix sync error: {e}")
        
        # Если нет сделки — обновляем регистрацию
        if not trip or not trip.bitrix_deal_id:
            reg = await crud.find_waiting_registration(session, driver.truck_number)
            if reg:
                await crud.update_registration_location(session, reg.id, lat, lon, address)
    
    # Формируем ответ
    response_lines = [
        "📍 <b>Локация сохранена!</b>\n",
        f"🏠 {address}",
    ]
    
    if distance_info:
        response_lines.append(f"\n📏 До терминала: <b>{distance_info['distance_km']:.0f} км</b>")
        response_lines.append(f"⏱️ Расчётное время: <b>{distance_info['eta_text']}</b>")
    
    if bitrix_synced:
        response_lines.append("\n✅ Данные отправлены брокеру")
    elif trip and trip.bitrix_deal_id:
        response_lines.append("\n⚠️ Ошибка синхронизации с CRM")
    else:
        response_lines.append("\n⏳ Ожидание привязки к сделке...")
    
    await message.answer(
        "\n".join(response_lines),
        reply_markup=keyboards.location_keyboard(),
        parse_mode="HTML"
    )


# ==================== ГЕОЛОКАЦИЯ БЕЗ СОСТОЯНИЯ ====================

@router.message(F.location)
async def handle_location_any_state(message: Message, state: FSMContext):
    """Обработка геолокации в любом состоянии (fallback)"""
    
    # Проверяем, есть ли у пользователя согласие
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        
        if not driver or not driver.consent_given:
            await message.answer(
                "❌ Для отправки геолокации сначала зарегистрируйтесь.\n"
                "Нажмите /start"
            )
            return
    
    # Устанавливаем состояние и обрабатываем
    await state.set_state(RegistrationStates.active_trip)
    await handle_location(message, state)


# ==================== АДРЕС ТЕРМИНАЛА ====================

@router.message(F.text == "🏭 Адрес терминала назначения")
async def send_terminal_address(message: Message, state: FSMContext):
    """Отправка адреса терминала назначения"""
    
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if not driver:
            await message.answer("❌ Сначала зарегистрируйтесь: /start")
            return
        
        trip = await crud.get_active_trip_by_driver(session, driver.id)
        
        if not trip or not trip.terminal_code:
            await message.answer(
                "❌ Терминал назначения не указан в заказе.\n"
                "Обратитесь к брокеру за уточнением."
            )
            return
        
        terminal = TERMINALS.get(trip.terminal_code)
        
        if terminal:
            # Формируем сообщение с доступными данными
            lines = [
                f"🏭 <b>Терминал назначения:</b>\n",
                f"<b>{terminal.get('name_ru', terminal.get('code', 'Терминал'))}</b>",
                f"📍 {terminal.get('address_ru', 'Адрес не указан')}",
            ]
            
            # Добавляем ссылки на карты если есть
            if terminal.get("google_maps"):
                lines.append(f"\n🗺️ <a href='{terminal['google_maps']}'>Google Maps</a>")
            if terminal.get("yandex_maps"):
                lines.append(f"🗺️ <a href='{terminal['yandex_maps']}'>Яндекс Карты</a>")
            
            await message.answer(
                "\n".join(lines),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            
            # Отправляем точку на карте
            if terminal.get("lat") and terminal.get("lon"):
                await message.answer_location(
                    latitude=terminal["lat"],
                    longitude=terminal["lon"]
                )
        else:
            await message.answer(
                f"🏭 Терминал: <b>{trip.terminal_code}</b>\n\n"
                f"❌ Подробная информация о терминале отсутствует в базе.\n"
                f"Обратитесь к брокеру за уточнением.",
                parse_mode="HTML"
            )


# ==================== УВЕДОМИТЬ О ПРИБЫТИИ ====================

@router.message(F.text == "📝 Уведомить о прибытии")
async def notify_arrival(message: Message, state: FSMContext):
    """Ручное уведомление о прибытии"""
    
    await message.answer(
        "📅 Когда планируете прибыть на терминал?",
        reply_markup=keyboards.arrival_date_keyboard()
    )


@router.callback_query(F.data.startswith("arrival_"))
async def process_arrival_date(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора даты прибытия"""
    
    action = callback.data.replace("arrival_", "")
    
    if action == "custom":
        await callback.message.answer(
            "📅 Введите дату прибытия в формате ДД.ММ.ГГГГ\n"
            "Например: 15.03.2026"
        )
        await state.set_state(ArrivalStates.waiting_arrival_date)
        await callback.answer()
        return
    
    # Расчёт даты
    today = datetime.now()
    if action == "today":
        arrival_date = today
    elif action == "tomorrow":
        arrival_date = today + timedelta(days=1)
    elif action == "2days":
        arrival_date = today + timedelta(days=2)
    elif action == "3days":
        arrival_date = today + timedelta(days=3)
    else:
        arrival_date = today
    
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, callback.from_user.id)
        if driver:
            trip = await crud.get_active_trip_by_driver(session, driver.id)
            
            if trip:
                trip.planned_arrival_date = arrival_date
                
                if trip.bitrix_deal_id:
                    await bitrix_client.update_deal(trip.bitrix_deal_id, {
                        settings.bitrix_field_planned_arrival: arrival_date.strftime("%Y-%m-%d")
                    })
                    
                    await bitrix_client.add_timeline_comment(
                        trip.bitrix_deal_id,
                        f"📅 Водитель указал планируемую дату прибытия: "
                        f"<b>{arrival_date.strftime('%d.%m.%Y')}</b>"
                    )
    
    await callback.message.answer(
        f"✅ Планируемая дата прибытия: <b>{arrival_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"Информация передана брокеру.",
        reply_markup=keyboards.location_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer("Дата сохранена!")


@router.message(ArrivalStates.waiting_arrival_date)
async def process_custom_arrival_date(message: Message, state: FSMContext):
    """Обработка ввода кастомной даты"""
    
    try:
        arrival_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты.\n"
            "Введите дату в формате ДД.ММ.ГГГГ (например: 15.03.2026)"
        )
        return
    
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if driver:
            trip = await crud.get_active_trip_by_driver(session, driver.id)
            
            if trip:
                trip.planned_arrival_date = arrival_date
                
                if trip.bitrix_deal_id:
                    await bitrix_client.update_deal(trip.bitrix_deal_id, {
                        settings.bitrix_field_planned_arrival: arrival_date.strftime("%Y-%m-%d")
                    })
    
    await message.answer(
        f"✅ Планируемая дата прибытия: <b>{arrival_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"Информация передана брокеру.",
        reply_markup=keyboards.location_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegistrationStates.active_trip)


# ==================== ЗАВЕРШИТЬ ПЕРЕВОЗКУ ====================

@router.message(F.text == "❌ Завершить текущую")
async def finish_trip(message: Message, state: FSMContext):
    """Завершение текущей перевозки"""
    
    await message.answer(
        "❓ Вы уверены, что хотите завершить текущую перевозку?",
        reply_markup=keyboards.confirm_keyboard()
    )


@router.callback_query(F.data == "confirm_yes")
async def confirm_finish_trip(callback: CallbackQuery, state: FSMContext):
    """Подтверждение завершения перевозки"""
    
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, callback.from_user.id)
        if driver:
            trip = await crud.get_active_trip_by_driver(session, driver.id)
            if trip:
                await crud.complete_trip(session, trip.id)
                
                if trip.bitrix_deal_id:
                    await bitrix_client.add_timeline_comment(
                        trip.bitrix_deal_id,
                        "🏁 Водитель завершил отслеживание перевозки через бота."
                    )
    
    await callback.message.answer(
        "✅ Перевозка завершена!\n\n"
        "Для начала новой перевозки нажмите /start",
        reply_markup=keyboards.remove_keyboard()
    )
    await state.clear()
    await callback.answer("Перевозка завершена")


@router.callback_query(F.data == "confirm_no")
async def cancel_finish_trip(callback: CallbackQuery, state: FSMContext):
    """Отмена завершения перевозки"""
    await callback.message.answer(
        "Отслеживание продолжается.",
        reply_markup=keyboards.location_keyboard()
    )
    await callback.answer()


# ==================== НОВАЯ ПЕРЕВОЗКА ====================

@router.message(F.text == "🔄 Новая перевозка")
async def new_trip(message: Message, state: FSMContext):
    """Начало новой перевозки"""
    
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if driver:
            # Завершаем текущий рейс если есть
            trip = await crud.get_active_trip_by_driver(session, driver.id)
            if trip:
                await crud.complete_trip(session, trip.id)
    
    await message.answer(
        "🔄 Начинаем новую перевозку.\n\n"
        "Введите номер тягача (без пробелов):",
        reply_markup=keyboards.cancel_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_truck_number)


# ==================== ОБНОВИТЬ СТАТУС ====================

@router.message(F.text == "🔄 Обновить статус")
async def update_status(message: Message, state: FSMContext):
    """Проверка статуса и привязки к сделке"""
    
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if not driver:
            await message.answer("❌ Сначала зарегистрируйтесь: /start")
            return
        
        trip = await crud.get_active_trip_by_driver(session, driver.id)
        
        if not trip:
            await message.answer(
                "❌ Нет активной перевозки.\n"
                "Нажмите /start для регистрации."
            )
            return
        
        # Пробуем найти сделку если ещё не привязана
        if not trip.bitrix_deal_id:
            deal = await bitrix_client.find_deal_by_truck_number(trip.truck_number)
            
            if deal:
                terminal_code = deal.get(settings.bitrix_field_terminal)
                terminal_info = TERMINALS.get(terminal_code, {})
                terminal_name = get_terminal_display_name(terminal_code)
                
                trip.bitrix_deal_id = int(deal["ID"])
                trip.bitrix_deal_title = deal.get("TITLE")
                trip.bitrix_stage_id = deal.get("STAGE_ID")
                trip.terminal_code = terminal_code
                trip.destination_address = terminal_info.get("address_ru")
                trip.destination_lat = terminal_info.get("lat")
                trip.destination_lon = terminal_info.get("lon")
                
                # Записываем Telegram ID в сделку
                await bitrix_client.update_driver_telegram_id(
                    int(deal["ID"]),
                    message.from_user.id,
                    message.from_user.username
                )
                
                await message.answer(
                    f"✅ <b>Сделка найдена и привязана!</b>\n\n"
                    f"📋 {deal.get('TITLE', 'Без названия')}\n"
                    f"🏭 Терминал: {terminal_name}\n\n"
                    f"Теперь ваше местоположение будет передаваться брокеру.",
                    reply_markup=keyboards.location_keyboard(),
                    parse_mode="HTML"
                )
                return
            else:
                await message.answer(
                    f"⏳ Сделка для номера {trip.truck_number} пока не создана.\n\n"
                    f"Продолжайте отправлять геолокацию — данные сохраняются.",
                    reply_markup=keyboards.waiting_keyboard()
                )
                return
        
        # Сделка уже привязана — показываем статус
        terminal_name = get_terminal_display_name(trip.terminal_code)
        await message.answer(
            f"📋 <b>Статус перевозки:</b>\n\n"
            f"🚛 Номер: {trip.truck_number}\n"
            f"📦 Сделка: #{trip.bitrix_deal_id}\n"
            f"🏭 Терминал: {terminal_name}\n"
            f"📅 Дней в пути: {trip.days_in_transit or 0}",
            reply_markup=keyboards.location_keyboard(),
            parse_mode="HTML"
        )


# ==================== CALLBACK: НАЧАТЬ ОТСЛЕЖИВАНИЕ ====================

@router.callback_query(F.data.startswith("start_trip_"))
async def start_trip_from_notification(callback: CallbackQuery, state: FSMContext):
    """Начало отслеживания из уведомления о новой сделке"""
    
    deal_id = int(callback.data.replace("start_trip_", ""))
    
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, callback.from_user.id)
        if not driver:
            await callback.answer("❌ Ошибка: водитель не найден")
            return
        
        # Получаем данные сделки
        deal = await bitrix_client.get_deal(deal_id)
        if not deal:
            await callback.answer("❌ Сделка не найдена")
            return
        
        # Завершаем предыдущий рейс если есть
        old_trip = await crud.get_active_trip_by_driver(session, driver.id)
        if old_trip:
            await crud.complete_trip(session, old_trip.id)
        
        # Определяем номер машины из сделки
        truck_number = (
            deal.get(settings.bitrix_field_truck_number_alt) or
            deal.get(settings.bitrix_field_truck_number, "")
        )
        
        terminal_code = deal.get(settings.bitrix_field_terminal)
        terminal_info = TERMINALS.get(terminal_code, {})
        terminal_name = get_terminal_display_name(terminal_code)
        
        # Создаём новый рейс
        trip = await crud.create_trip(
            session,
            driver_id=driver.id,
            truck_number=truck_number,
            bitrix_deal_id=deal_id,
            bitrix_deal_title=deal.get("TITLE"),
            bitrix_stage_id=deal.get("STAGE_ID"),
            terminal_code=terminal_code,
            destination_address=terminal_info.get("address_ru"),
            destination_lat=terminal_info.get("lat"),
            destination_lon=terminal_info.get("lon"),
        )
        
        # Обновляем номер машины в профиле водителя
        driver.truck_number = truck_number
        
        await bitrix_client.add_timeline_comment(
            deal_id,
            f"🚛 Водитель подтвердил начало отслеживания через Telegram-бот."
        )
    
    await callback.message.answer(
        f"✅ <b>Отслеживание активировано!</b>\n\n"
        f"📋 {deal.get('TITLE', 'Без названия')}\n"
        f"🏭 Терминал: {terminal_name}\n\n"
        f"Отправьте своё местоположение:",
        reply_markup=keyboards.location_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegistrationStates.active_trip)
    await callback.answer("Отслеживание активировано!")


@router.callback_query(F.data == "decline_trip")
async def decline_trip_notification(callback: CallbackQuery):
    """Отклонение уведомления о новой сделке"""
    await callback.message.answer(
        "Уведомление отклонено.\n"
        "Если передумаете — нажмите /start"
    )
    await callback.answer()


# ==================== КОМАНДА ПОМОЩЬ ====================

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда помощи"""
    await message.answer(
        "🚛 <b>Бот отслеживания перевозок</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — Начать работу / новая перевозка\n"
        "/help — Справка\n\n"
        "<b>Кнопки:</b>\n"
        "📍 Отправить местоположение — передать геолокацию\n"
        "🏭 Адрес терминала — показать адрес назначения\n"
        "📝 Уведомить о прибытии — указать дату прибытия\n"
        "🔄 Новая перевозка — начать новый рейс\n"
        "❌ Завершить текущую — завершить отслеживание\n\n"
        "По вопросам обращайтесь к диспетчеру.",
        parse_mode="HTML"
    )
