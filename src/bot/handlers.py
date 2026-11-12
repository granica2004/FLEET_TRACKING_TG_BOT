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
from src.config import get_settings, TERMINALS, terminal_name
from src.services.notify import fire, is_admin
from src.services.trips import deal_trip_fields, apply_deal_to_trip, deal_link
from html import escape

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


def get_terminal_display_name(terminal_code) -> str:
    """Получить отображаемое название терминала"""
    return terminal_name(terminal_code)


BLOCKED_TEXT = "⛔ Доступ к боту закрыт. Обратитесь к диспетчеру."


def _admin_kb():
    from src.bot.admin import trip_button, driver_reply_button
    return trip_button, driver_reply_button


CONSENT_TEXT = (
    "🚛 <b>Бот отслеживания перевозок ГРАНИЦА 2004</b>\n\n"
    "Бот передаёт местоположение машины на пути к таможенному терминалу.\n\n"
    "Для работы нужно ваше согласие: координаты и адрес вашей машины во время рейса увидят "
    "таможенный брокер, отправитель груза и получатель груза. Данные используются только "
    "для контроля доставки и передаются только во время активного рейса.\n\n"
    "Нажмите кнопку ниже, если согласны:"
)


async def send_consent_request(message: Message, state: FSMContext):
    await message.answer(CONSENT_TEXT, reply_markup=keyboards.consent_keyboard(), parse_mode="HTML")
    await state.set_state(RegistrationStates.waiting_consent)


# ==================== КОМАНДА /start ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    
    async with get_session() as session:
        # Проверяем, есть ли водитель в базе
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        
        if driver and not driver.is_active:
            await message.answer(BLOCKED_TEXT, reply_markup=keyboards.remove_keyboard())
            await state.clear()
            return
        
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
            
            await send_consent_request(message, state)


# ==================== СОГЛАСИЕ ====================

@router.message(RegistrationStates.waiting_consent, F.text.contains("согласие"))
async def process_consent(message: Message, state: FSMContext):
    """Обработка согласия на передачу геолокации"""
    
    data = await state.get_data()
    async with get_session() as session:
        driver = await crud.update_driver_consent(session, message.from_user.id, True)
        # Водитель пришёл по ссылке на конкретный рейс — подключаем сразу
        if data.get("invite_trip_id") and driver:
            from src.bot.roles import attach_driver, driver_trip_text
            trip = await crud.get_trip_by_id(session, data["invite_trip_id"])
            if trip and trip.status == "active":
                await attach_driver(session, message.bot, driver, trip)
                text = await driver_trip_text(trip)
                await state.set_state(RegistrationStates.active_trip)
                await state.update_data(invite_trip_id=None)
                await message.answer(text, reply_markup=keyboards.location_keyboard(), parse_mode="HTML")
                return
    
    await message.answer(
        "✅ Согласие получено! Спасибо.\n\n"
        "Теперь введите <b>номер тягача</b> (без пробелов):\n"
        "Например: А123ВС77 или 60144OBA. Если везёте контейнер — можно номер контейнера.",
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
        
        # Рейс с этим номером уже создан брокером/админом и ждёт водителя
        prepared = await crud.get_driverless_trip_by_truck(session, truck)
        if prepared:
            from src.bot.roles import attach_driver, driver_trip_text
            await attach_driver(session, message.bot, driver, prepared)
            if not prepared.bitrix_deal_id:
                try:
                    found = await bitrix_client.find_deal_by_truck_number(truck)
                except Exception as e:
                    logger.error(f"Bitrix search failed: {e}")
                    found = None
                if found:
                    apply_deal_to_trip(prepared, found)
                    await bitrix_client.update_driver_telegram_id(int(found["ID"]), message.from_user.id,
                                                                  message.from_user.username)
            text = await driver_trip_text(prepared)
            await message.answer(text, reply_markup=keyboards.location_keyboard(), parse_mode="HTML")
            await state.set_state(RegistrationStates.active_trip)
            return
        
        # Ищем сделку в Битрикс24 (включая стадию "Новая")
        deal = await bitrix_client.find_deal_by_truck_number(truck)
        
        # Закрываем прежний активный рейс водителя, чтобы не было двух активных
        old_trip = await crud.get_active_trip_by_driver(session, driver.id)
        if old_trip:
            await crud.complete_trip(session, old_trip.id)
        
        if deal:
            # Сделка найдена — создаём рейс
            fields = deal_trip_fields(deal)
            terminal_code = fields["terminal_code"]
            terminal_info = TERMINALS.get(terminal_code or "", {})
            terminal_name = get_terminal_display_name(terminal_code)
            fields.pop("bitrix_deal_id")
            
            trip = await crud.create_trip(
                session,
                driver_id=driver.id,
                truck_number=truck,
                trailer_number=None,
                bitrix_deal_id=int(deal["ID"]),
                **fields,
            )
            
            from src.services import events
            await events.on_trip_started(session, trip)
            trip_button, _ = _admin_kb()
            fire("reg", f"🆕 <b>Водитель зарегистрировался</b>\n"
                        f"🚛 {escape(truck)} · {escape(message.from_user.full_name)}\n"
                        f"📋 {deal_link(int(deal['ID']), deal.get('TITLE'))}\n"
                        f"🏭 {escape(terminal_name)}", trip_button(trip.id))
            
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
            
            trip_button, _ = _admin_kb()
            fire("reg", f"🆕 <b>Водитель зарегистрировался, сделка не найдена</b>\n"
                        f"🚛 {escape(truck)} · {escape(message.from_user.full_name)}\n"
                        f"Проверьте номер в сделке или привяжите вручную.", trip_button(trip.id))
            
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
    
    # Получаем адрес и страну по координатам
    country = None
    try:
        address, country = await maps_service.reverse_details(lat, lon)
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
        if not driver.is_active:
            await message.answer(BLOCKED_TEXT)
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
        
        if trip:
            trip.silence_alert_at = None
        prev_location = await crud.get_last_trip_location(session, trip) if trip else None
        
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
        location.country_code = (country or "").lower() or None
        
        # События: граница, машина у терминала
        if trip:
            try:
                from src.services import events
                await events.on_location(session, trip, location, prev_location)
            except Exception as e:
                logger.exception(f"Location events failed: {e}")
        
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
            if not bitrix_synced:
                trip_button, _ = _admin_kb()
                fire("error", f"⚠️ <b>Не удалось записать геопозицию в сделку</b> "
                              f"#{trip.bitrix_deal_id} ({escape(trip.truck_number)})", trip_button(trip.id))
        
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

@router.message(F.text.in_(keyboards.TERMINAL_BUTTON_TEXTS))
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
        
        terminal = TERMINALS.get(str(trip.terminal_code), {})
        
        lines = [
            "📍 <b>Терминал прибытия</b>\n",
            f"<b>{escape(terminal.get('code', str(trip.terminal_code)))}</b>",
        ]
        if terminal.get("name_ru"):
            lines.append(escape(terminal["name_ru"]))
        if terminal.get("address_ru"):
            lines.append(f"🏠 {escape(terminal['address_ru'])}")
        if terminal.get("address_en"):
            lines.append(f"🏠 {escape(terminal['address_en'])}")
        if terminal.get("hours"):
            lines.append(f"🕐 {escape(terminal['hours'])}")
        if terminal.get("phone"):
            lines.append(f"📞 {escape(terminal['phone'])}")
        
        has_coords = terminal.get("lat") and terminal.get("lon")
        if not has_coords:
            lines.append("\n⚠️ Точный адрес терминала пока не внесён. Уточните у диспетчера — "
                         "напишите сообщение прямо в этот чат.")
        
        await message.answer(
            "\n".join(lines),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboards.terminal_nav_keyboard(terminal["lat"], terminal["lon"]) if has_coords else None,
        )
        
        # Точка на карте — по ней можно построить маршрут прямо в Telegram
        if has_coords:
            await message.answer_venue(
                latitude=terminal["lat"],
                longitude=terminal["lon"],
                title=terminal.get("code", "Терминал"),
                address=terminal.get("address_ru", ""),
            )


# ==================== УВЕДОМИТЬ О ПРИБЫТИИ ====================

@router.message(F.text.in_(keyboards.ARRIVAL_BUTTON_TEXTS))
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
                from src.services import events
                await events.on_finished(session, trip)
                trip_button, _ = _admin_kb()
                fire("done", f"🏁 <b>Водитель сам завершил рейс</b> {escape(trip.truck_number)}\n"
                             f"📋 {deal_link(trip.bitrix_deal_id, trip.bitrix_deal_title)}", trip_button(trip.id))
    
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
                
                apply_deal_to_trip(trip, deal)
                
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
        fields = deal_trip_fields(deal)
        fields.pop("bitrix_deal_id")
        trip = await crud.create_trip(
            session,
            driver_id=driver.id,
            truck_number=truck_number or driver.truck_number or "—",
            bitrix_deal_id=deal_id,
            **fields,
        )
        
        # Обновляем номер машины в профиле водителя
        if truck_number:
            driver.truck_number = truck_number.upper().replace(" ", "")
        
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
        "📍 Терминал прибытия — адрес, точка на карте и маршрут в навигаторе\n"
        "📝 Дата прибытия — указать планируемую дату прибытия\n"
        "🔄 Новая перевозка — начать новый рейс\n"
        "❌ Завершить текущую — завершить отслеживание\n\n"
        "По вопросам обращайтесь к диспетчеру.",
        parse_mode="HTML"
    )



# ==================== СООБЩЕНИЯ ВОДИТЕЛЯ ДИСПЕТЧЕРУ ====================

@router.message(F.text & ~F.text.startswith("/"))
async def forward_to_dispatcher(message: Message, state: FSMContext):
    """Любой текст, не подошедший под кнопки и шаги, пересылаем админам."""
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if not driver or not driver.consent_given:
            await message.answer("Для начала работы нажмите /start")
            return
        if not driver.is_active:
            await message.answer(BLOCKED_TEXT)
            return
        trip = await crud.get_active_trip_by_driver(session, driver.id)
    _, driver_reply_button = _admin_kb()
    trip_info = ""
    if trip:
        trip_info = f"\n🚛 {escape(trip.truck_number)} · {deal_link(trip.bitrix_deal_id, trip.bitrix_deal_title)}"
    from src.services.trips import driver_label
    from src.services.access import all_admin_ids
    for admin_id in all_admin_ids():
        try:
            await message.bot.send_message(
                admin_id,
                f"💬 <b>Сообщение от водителя</b> {driver_label(driver)}{trip_info}\n\n{escape(message.text)}",
                reply_markup=driver_reply_button(driver.id), parse_mode="HTML", disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning(f"Cannot forward driver message to admin {admin_id}: {e}")
    await message.answer(
        "✉️ Сообщение передано диспетчеру.",
        reply_markup=keyboards.location_keyboard() if trip else None,
    )
