"""
Сценарий водителя: согласие, регистрация по номеру, геолокация, терминал, дата прибытия,
завершение рейса. Тексты — на языке водителя (src/i18n.py). Уведомления админам — на русском.
"""

import re
from datetime import datetime, timedelta
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from src.bot import keyboards
from src.bot.states import ArrivalStates, RegistrationStates
from src.config import TERMINALS, get_settings
from src.db import crud
from src.db.database import get_session
from src.i18n import V, duration, t, terminal_address, terminal_name
from src.services.bitrix import bitrix_client
from src.services.deal_sync import announce_link
from src.services.geocoder import maps_service
from src.services.notify import fire
from src.services.trips import apply_deal_to_trip, deal_link, deal_trip_fields

settings = get_settings()
router = Router()

# Российский номер: А123ВС77 или А123ВС777
RU_PLATE_REGEX = r'^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$'
# Иностранный номер (свободнее)
FOREIGN_PLATE_REGEX = r'^[A-Z0-9]{2,10}$'


def validate_plate_number(plate: str) -> bool:
    """Проверка формата номера транспортного средства"""
    plate_clean = plate.upper().replace(" ", "").replace("-", "")
    if re.match(RU_PLATE_REGEX, plate_clean) or re.match(FOREIGN_PLATE_REGEX, plate_clean):
        return True
    if "/" in plate_clean:
        return all(len(p) >= 3 for p in plate_clean.split("/"))
    return len(plate_clean) >= 3


def _admin_kb():
    from src.bot.admin import driver_reply_button, trip_button
    return trip_button, driver_reply_button


def _title(lang, deal_or_title) -> str:
    title = deal_or_title.get("TITLE") if isinstance(deal_or_title, dict) else deal_or_title
    return escape(title or t(lang, "unnamed"))


async def send_consent_request(message: Message, state: FSMContext, lang: str = "ru"):
    await message.answer(t(lang, "consent_text"), reply_markup=keyboards.consent_keyboard(lang), parse_mode="HTML")
    await state.set_state(RegistrationStates.waiting_consent)


# ==================== /start ВОДИТЕЛЯ ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, lang: str = "ru", user=None):
    """Сценарий водителя. user — когда вызывается из колбэка (выбор языка)."""
    user = user or message.from_user
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, user.id)

        if driver and not driver.is_active:
            await message.answer(t(lang, "blocked"), reply_markup=keyboards.remove_keyboard())
            await state.clear()
            return

        if driver and driver.consent_given:
            trip = await crud.get_active_trip_by_driver(session, driver.id)
            if trip:
                await message.answer(
                    t(lang, "welcome_back_trip", truck=escape(trip.truck_number),
                      terminal=escape(terminal_name(lang, trip.terminal_code))),
                    reply_markup=keyboards.location_keyboard(lang),
                )
                await state.set_state(RegistrationStates.active_trip)
            else:
                await message.answer(
                    t(lang, "welcome_back_new", name=escape(driver.first_name or t(lang, "driver_word"))),
                    reply_markup=keyboards.cancel_keyboard(lang),
                )
                await state.set_state(RegistrationStates.waiting_truck_number)
            return

        if not driver:
            await crud.create_driver(
                session, telegram_id=user.id, username=user.username,
                first_name=user.first_name, last_name=user.last_name,
            )
    await send_consent_request(message, state, lang)


# ==================== СОГЛАСИЕ ====================

def _is_consent(text: str) -> bool:
    return bool(text) and (text in V("btn_consent") or "согласие" in text)


@router.message(RegistrationStates.waiting_consent, F.text.func(_is_consent))
async def process_consent(message: Message, state: FSMContext, lang: str = "ru"):
    data = await state.get_data()
    async with get_session() as session:
        driver = await crud.update_driver_consent(session, message.from_user.id, True)
        # Водитель пришёл по ссылке на конкретный рейс — подключаем сразу
        if data.get("invite_trip_id") and driver:
            from src.bot.roles import attach_driver, driver_trip_text
            trip = await crud.get_trip_by_id(session, data["invite_trip_id"])
            if trip and trip.status == "active":
                await attach_driver(session, message.bot, driver, trip, how="водитель открыл ссылку-приглашение")
                text = driver_trip_text(lang, trip)
                await state.set_state(RegistrationStates.active_trip)
                await state.update_data(invite_trip_id=None)
                await message.answer(text, reply_markup=keyboards.location_keyboard(lang), parse_mode="HTML")
                return

    await message.answer(t(lang, "consent_ok"), reply_markup=keyboards.cancel_keyboard(lang), parse_mode="HTML")
    await state.set_state(RegistrationStates.waiting_truck_number)


# ==================== НОМЕР ТЯГАЧА ====================

@router.message(RegistrationStates.waiting_truck_number)
async def process_truck_number(message: Message, state: FSMContext, lang: str = "ru"):
    if message.text in V("btn_cancel"):
        await message.answer(t(lang, "reg_cancelled"), reply_markup=keyboards.remove_keyboard())
        await state.clear()
        return
    if not message.text:
        await message.answer(t(lang, "bad_plate"))
        return

    truck = message.text.strip().upper().replace(" ", "").replace("-", "")
    if not validate_plate_number(truck):
        await message.answer(t(lang, "bad_plate"))
        return
    await state.update_data(truck_number=truck)

    async with get_session() as session:
        driver = await crud.update_driver_transport(session, message.from_user.id, truck, None)

        # Рейс с этим номером уже создан брокером/админом и ждёт водителя
        prepared = await crud.get_driverless_trip_by_truck(session, truck)
        if prepared:
            from src.bot.roles import attach_driver, driver_trip_text
            if not prepared.bitrix_deal_id:
                try:
                    found = await bitrix_client.find_deal_by_truck_number(truck)
                except Exception as e:
                    logger.error(f"Bitrix search failed: {e}")
                    found = None
                if found:
                    apply_deal_to_trip(prepared, found)
            await attach_driver(session, message.bot, driver, prepared,
                                how="водитель ввёл номер заранее созданного рейса")
            await message.answer(driver_trip_text(lang, prepared), reply_markup=keyboards.location_keyboard(lang),
                                 parse_mode="HTML")
            await state.set_state(RegistrationStates.active_trip)
            return

        deal = await bitrix_client.find_deal_by_truck_number(truck)

        # Закрываем прежний активный рейс водителя, чтобы не было двух активных
        old_trip = await crud.get_active_trip_by_driver(session, driver.id)
        if old_trip:
            await crud.complete_trip(session, old_trip.id)

        trip_button, _ = _admin_kb()
        if deal:
            fields = deal_trip_fields(deal)
            terminal_code = fields["terminal_code"]
            fields.pop("bitrix_deal_id")
            trip = await crud.create_trip(
                session, driver_id=driver.id, truck_number=truck, trailer_number=None,
                bitrix_deal_id=int(deal["ID"]), **fields,
            )
            await bitrix_client.update_driver_telegram_id(int(deal["ID"]), message.from_user.id,
                                                          message.from_user.username)
            await announce_link(session, trip, driver, "водитель зарегистрировался, сделка найдена по номеру")
            from src.services import events
            await events.on_trip_started(session, trip)
            fire("reg", f"🆕 <b>Водитель зарегистрировался</b>\n"
                        f"🚛 {escape(truck)} · {escape(message.from_user.full_name)}\n"
                        f"📋 {deal_link(int(deal['ID']), deal.get('TITLE'))}\n"
                        f"🏭 {escape(terminal_name('ru', terminal_code))}", trip_button(trip.id))
            await message.answer(
                t(lang, "reg_done_deal", truck=escape(truck), title=_title(lang, deal),
                  terminal=escape(terminal_name(lang, terminal_code)),
                  address=escape(terminal_address(lang, terminal_code))),
                reply_markup=keyboards.location_keyboard(lang), parse_mode="HTML",
            )
        else:
            await crud.create_driver_registration(session, message.from_user.id, truck, None)
            trip = await crud.create_trip(session, driver_id=driver.id, truck_number=truck, trailer_number=None)
            fire("reg", f"🆕 <b>Водитель зарегистрировался, сделка не найдена</b>\n"
                        f"🚛 {escape(truck)} · {escape(message.from_user.full_name)}\n"
                        f"Проверьте номер в сделке или привяжите вручную.", trip_button(trip.id))
            await message.answer(t(lang, "reg_done_wait", truck=escape(truck)),
                                 reply_markup=keyboards.waiting_keyboard(lang), parse_mode="HTML")
        await state.set_state(RegistrationStates.active_trip)


# ==================== ГЕОЛОКАЦИЯ ====================

@router.message(RegistrationStates.active_trip, F.location)
async def handle_location(message: Message, state: FSMContext, lang: str = "ru"):
    lat = message.location.latitude
    lon = message.location.longitude
    logger.info(f"Received location from {message.from_user.id}: {lat}, {lon}")

    country = None
    try:
        address, country = await maps_service.reverse_details(lat, lon)
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        address = None
    if not address:
        address = f"{lat:.6f}, {lon:.6f}"

    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if not driver:
            await message.answer(t(lang, "driver_not_found"))
            return
        if not driver.is_active:
            await message.answer(t(lang, "blocked"))
            return

        trip = await crud.get_active_trip_by_driver(session, driver.id)

        distance_info = None
        if trip and trip.terminal_code:
            try:
                distance_info = await maps_service.get_distance_to_terminal(lat, lon, trip.terminal_code)
            except Exception as e:
                logger.error(f"Distance calculation error: {e}")

        if trip:
            trip.silence_alert_at = None
        prev_location = await crud.get_last_trip_location(session, trip) if trip else None

        location = await crud.save_location(
            session, driver_id=driver.id, latitude=lat, longitude=lon, address=address,
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

        bitrix_synced = False
        if trip and trip.bitrix_deal_id:
            try:
                success = await bitrix_client.add_location_comment(
                    trip.bitrix_deal_id, address, lat, lon,
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

        if not trip or not trip.bitrix_deal_id:
            reg = await crud.find_waiting_registration(session, driver.truck_number) if driver.truck_number else None
            if reg:
                await crud.update_registration_location(session, reg.id, lat, lon, address)

    lines = [t(lang, "loc_saved"), f"🏠 {escape(address)}"]
    if distance_info:
        lines.append(t(lang, "loc_to_terminal", km=f"{distance_info['distance_km']:.0f}"))
        eta = duration(lang, distance_info.get("duration_minutes"))
        if eta:
            lines.append(t(lang, "loc_eta", eta=eta))
    if bitrix_synced:
        lines.append(t(lang, "loc_synced"))
    elif trip and trip.bitrix_deal_id:
        lines.append(t(lang, "loc_sync_err"))
    else:
        lines.append(t(lang, "loc_waiting"))
    await message.answer("\n".join(lines), reply_markup=keyboards.location_keyboard(lang), parse_mode="HTML")


@router.message(F.location)
async def handle_location_any_state(message: Message, state: FSMContext, lang: str = "ru"):
    """Геолокация в любом состоянии"""
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
    if not driver or not driver.consent_given:
        await message.answer(t(lang, "loc_register_first"))
        return
    await state.set_state(RegistrationStates.active_trip)
    await handle_location(message, state, lang)


# ==================== ТЕРМИНАЛ ПРИБЫТИЯ ====================

@router.message(F.text.in_(keyboards.TERMINAL_BUTTON_TEXTS))
async def send_terminal_address(message: Message, state: FSMContext, lang: str = "ru"):
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if not driver:
            await message.answer(t(lang, "register_first"))
            return
        trip = await crud.get_active_trip_by_driver(session, driver.id)
    if not trip or not trip.terminal_code:
        await message.answer(t(lang, "no_terminal"))
        return

    terminal = TERMINALS.get(str(trip.terminal_code), {})
    lines = [t(lang, "terminal_title"), f"<b>{escape(terminal_name(lang, trip.terminal_code).split(' — ')[0])}</b>"]
    if lang == "ru" and terminal.get("name_ru"):
        lines.append(escape(terminal["name_ru"]))
    elif terminal.get("name_en"):
        lines.append(escape(terminal["name_en"]))
    addr = terminal_address(lang, trip.terminal_code)
    if addr:
        lines.append(f"🏠 {escape(addr)}")
    if lang != "ru" and terminal.get("address_ru"):
        lines.append(f"🏠 {escape(terminal['address_ru'])}")  # русский адрес — показать на въезде/охране
    if terminal.get("hours"):
        lines.append(f"🕐 {escape(terminal['hours'])}")
    if terminal.get("phone"):
        lines.append(f"📞 {escape(terminal['phone'])}")

    has_coords = terminal.get("lat") and terminal.get("lon")
    if not has_coords:
        lines.append(t(lang, "terminal_no_coords"))
    await message.answer(
        "\n".join(lines), parse_mode="HTML", disable_web_page_preview=True,
        reply_markup=keyboards.terminal_nav_keyboard(terminal["lat"], terminal["lon"], lang) if has_coords else None,
    )
    if has_coords:
        await message.answer_venue(
            latitude=terminal["lat"], longitude=terminal["lon"],
            title=terminal_name(lang, trip.terminal_code).split(" — ")[0] or t(lang, "terminal_word"),
            address=addr,
        )


# ==================== ДАТА ПРИБЫТИЯ ====================

@router.message(F.text.in_(keyboards.ARRIVAL_BUTTON_TEXTS))
async def notify_arrival(message: Message, state: FSMContext, lang: str = "ru"):
    await message.answer(t(lang, "arrival_ask"), reply_markup=keyboards.arrival_date_keyboard(lang))


async def _save_arrival(user_id: int, arrival_date: datetime):
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, user_id)
        trip = await crud.get_active_trip_by_driver(session, driver.id) if driver else None
        if not trip:
            return
        trip.planned_arrival_date = arrival_date
        if trip.bitrix_deal_id:
            await bitrix_client.update_deal(trip.bitrix_deal_id, {
                settings.bitrix_field_planned_arrival: arrival_date.strftime("%Y-%m-%d")})
            await bitrix_client.add_timeline_comment(
                trip.bitrix_deal_id,
                f"📅 Водитель указал планируемую дату прибытия: <b>{arrival_date.strftime('%d.%m.%Y')}</b>")


@router.callback_query(F.data.startswith("arrival_"))
async def process_arrival_date(callback: CallbackQuery, state: FSMContext, lang: str = "ru"):
    action = callback.data.replace("arrival_", "")
    if action == "custom":
        await callback.message.answer(t(lang, "arrival_enter_date"))
        await state.set_state(ArrivalStates.waiting_arrival_date)
        await callback.answer()
        return
    days = {"today": 0, "tomorrow": 1, "2days": 2, "3days": 3}.get(action, 0)
    arrival_date = datetime.utcnow() + timedelta(hours=3, days=days)
    await _save_arrival(callback.from_user.id, arrival_date)
    await callback.message.answer(
        t(lang, "arrival_saved", date=arrival_date.strftime("%d.%m.%Y")),
        reply_markup=keyboards.location_keyboard(lang), parse_mode="HTML",
    )
    await callback.answer(t(lang, "arrival_saved_short"))


@router.message(ArrivalStates.waiting_arrival_date)
async def process_custom_arrival_date(message: Message, state: FSMContext, lang: str = "ru"):
    try:
        arrival_date = datetime.strptime((message.text or "").strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer(t(lang, "bad_date"))
        return
    await _save_arrival(message.from_user.id, arrival_date)
    await message.answer(
        t(lang, "arrival_saved", date=arrival_date.strftime("%d.%m.%Y")),
        reply_markup=keyboards.location_keyboard(lang), parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.active_trip)


# ==================== ЗАВЕРШЕНИЕ ====================

@router.message(F.text.in_(V("btn_finish")))
async def finish_trip(message: Message, state: FSMContext, lang: str = "ru"):
    await message.answer(t(lang, "finish_confirm"), reply_markup=keyboards.confirm_keyboard(lang))


@router.callback_query(F.data == "confirm_yes")
async def confirm_finish_trip(callback: CallbackQuery, state: FSMContext, lang: str = "ru"):
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, callback.from_user.id)
        trip = await crud.get_active_trip_by_driver(session, driver.id) if driver else None
        if trip:
            await crud.complete_trip(session, trip.id)
            if trip.bitrix_deal_id:
                await bitrix_client.add_timeline_comment(
                    trip.bitrix_deal_id, "🏁 Водитель завершил отслеживание перевозки через бота.")
            from src.services import events
            await events.on_finished(session, trip)
            trip_button, _ = _admin_kb()
            fire("done", f"🏁 <b>Водитель сам завершил рейс</b> {escape(trip.truck_number)}\n"
                         f"📋 {deal_link(trip.bitrix_deal_id, trip.bitrix_deal_title)}", trip_button(trip.id))
    await callback.message.answer(t(lang, "trip_finished"), reply_markup=keyboards.remove_keyboard())
    await state.clear()
    await callback.answer(t(lang, "trip_finished_short"))


@router.callback_query(F.data == "confirm_no")
async def cancel_finish_trip(callback: CallbackQuery, state: FSMContext, lang: str = "ru"):
    await callback.message.answer(t(lang, "tracking_continues"), reply_markup=keyboards.location_keyboard(lang))
    await callback.answer()


# ==================== НОВАЯ ПЕРЕВОЗКА ====================

@router.message(F.text.in_(V("btn_new_trip")))
async def new_trip(message: Message, state: FSMContext, lang: str = "ru"):
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        trip = await crud.get_active_trip_by_driver(session, driver.id) if driver else None
        if trip:
            await crud.complete_trip(session, trip.id)
    await message.answer(t(lang, "new_trip_enter"), reply_markup=keyboards.cancel_keyboard(lang))
    await state.set_state(RegistrationStates.waiting_truck_number)


# ==================== ОБНОВИТЬ СТАТУС ====================

@router.message(F.text.in_(V("btn_refresh_status")))
async def update_status(message: Message, state: FSMContext, lang: str = "ru"):
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if not driver:
            await message.answer(t(lang, "register_first"))
            return
        trip = await crud.get_active_trip_by_driver(session, driver.id)
        if not trip:
            await message.answer(t(lang, "no_active_trip"))
            return

        if not trip.bitrix_deal_id:
            deal = await bitrix_client.find_deal_by_truck_number(trip.truck_number)
            if not deal:
                await message.answer(t(lang, "deal_not_yet", truck=escape(trip.truck_number)),
                                     reply_markup=keyboards.waiting_keyboard(lang))
                return
            apply_deal_to_trip(trip, deal)
            await bitrix_client.update_driver_telegram_id(int(deal["ID"]), message.from_user.id,
                                                          message.from_user.username)
            await announce_link(session, trip, driver, "водитель нажал «Обновить статус», сделка найдена по номеру")
            await crud.cancel_waiting_registrations(session, message.from_user.id)
            from src.services import events
            await events.on_trip_started(session, trip)
            await message.answer(
                t(lang, "deal_found_linked", title=_title(lang, deal),
                  terminal=escape(terminal_name(lang, trip.terminal_code))),
                reply_markup=keyboards.location_keyboard(lang), parse_mode="HTML",
            )
            return

        await message.answer(
            t(lang, "status", truck=escape(trip.truck_number), deal=trip.bitrix_deal_id,
              terminal=escape(terminal_name(lang, trip.terminal_code)), days=trip.days_in_transit or 0),
            reply_markup=keyboards.location_keyboard(lang), parse_mode="HTML",
        )


# ==================== НАЧАТЬ ОТСЛЕЖИВАНИЕ ИЗ УВЕДОМЛЕНИЯ ====================

@router.callback_query(F.data.startswith("start_trip_"))
async def start_trip_from_notification(callback: CallbackQuery, state: FSMContext, lang: str = "ru"):
    deal_id = int(callback.data.replace("start_trip_", ""))
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, callback.from_user.id)
        if not driver:
            await callback.answer(t(lang, "driver_not_found"))
            return
        deal = await bitrix_client.get_deal(deal_id)
        if not deal:
            await callback.answer(t(lang, "deal_not_found_short"))
            return
        old_trip = await crud.get_active_trip_by_driver(session, driver.id)
        if old_trip:
            await crud.complete_trip(session, old_trip.id)

        truck_number = (deal.get(settings.bitrix_field_truck_number_alt)
                        or deal.get(settings.bitrix_field_truck_number, ""))
        fields = deal_trip_fields(deal)
        fields.pop("bitrix_deal_id")
        trip = await crud.create_trip(
            session, driver_id=driver.id, truck_number=truck_number or driver.truck_number or "—",
            bitrix_deal_id=deal_id, **fields,
        )
        if truck_number:
            driver.truck_number = truck_number.upper().replace(" ", "")
        await bitrix_client.update_driver_telegram_id(deal_id, driver.telegram_id, driver.username)
        await announce_link(session, trip, driver, "водитель подтвердил начало отслеживания из уведомления бота")
        from src.services import events
        await events.on_trip_started(session, trip)
        terminal = terminal_name(lang, trip.terminal_code)

    await callback.message.answer(
        t(lang, "tracking_activated", title=_title(lang, deal), terminal=escape(terminal)),
        reply_markup=keyboards.location_keyboard(lang), parse_mode="HTML",
    )
    await state.set_state(RegistrationStates.active_trip)
    await callback.answer(t(lang, "tracking_activated_short"))


@router.callback_query(F.data == "decline_trip")
async def decline_trip_notification(callback: CallbackQuery, lang: str = "ru"):
    await callback.message.answer(t(lang, "offer_declined"))
    await callback.answer()


# ==================== ПОМОЩЬ ====================

@router.message(Command("help"))
async def cmd_help(message: Message, lang: str = "ru"):
    await message.answer(t(lang, "help"), parse_mode="HTML")


# ==================== СООБЩЕНИЯ ВОДИТЕЛЯ ДИСПЕТЧЕРУ ====================

@router.message(F.text & ~F.text.startswith("/"))
async def forward_to_dispatcher(message: Message, state: FSMContext, lang: str = "ru"):
    """Любой текст, не подошедший под кнопки и шаги, пересылаем админам."""
    async with get_session() as session:
        driver = await crud.get_driver_by_telegram_id(session, message.from_user.id)
        if not driver or not driver.consent_given:
            await message.answer(t(lang, "press_start"))
            return
        if not driver.is_active:
            await message.answer(t(lang, "blocked"))
            return
        trip = await crud.get_active_trip_by_driver(session, driver.id)
    _, driver_reply_button = _admin_kb()
    trip_info = ""
    if trip:
        trip_info = f"\n🚛 {escape(trip.truck_number)} · {deal_link(trip.bitrix_deal_id, trip.bitrix_deal_title)}"
    from src.services.access import all_admin_ids
    from src.services.trips import driver_label
    for admin_id in all_admin_ids():
        try:
            await message.bot.send_message(
                admin_id,
                f"💬 <b>Сообщение от водителя</b> {driver_label(driver)}{trip_info}\n\n{escape(message.text)}",
                reply_markup=driver_reply_button(driver.id), parse_mode="HTML", disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning(f"Cannot forward driver message to admin {admin_id}: {e}")
    await message.answer(t(lang, "sent_to_dispatcher"),
                         reply_markup=keyboards.location_keyboard(lang) if trip else None)
