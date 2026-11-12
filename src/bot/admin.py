"""
Админка в боте: /admin (только для ADMIN_IDS).

Сводка, рейсы в пути, рейсы без сделки, молчащие водители, карточка рейса
(запрос геопозиции, сообщение водителю, привязка к сделке, завершение),
водители (блокировка), терминалы, настройка уведомлений.
"""

from datetime import datetime, timedelta
from html import escape
from typing import List, Optional

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from loguru import logger

from src.bot import keyboards
from src.config import TERMINALS, get_settings, terminal_name
from src.db import crud
from src.db.database import get_session
from src.services.bitrix import bitrix_client
from src.services.notify import EVENT_TITLES, is_admin
from src.services.trips import (
    ago, apply_deal_to_trip, deal_link, driver_label, msk,
)

settings = get_settings()
router = Router(name="admin")

PAGE = 8


class AdminFilter(BaseFilter):
    async def __call__(self, event) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and is_admin(user.id))


class AdminStates(StatesGroup):
    bind_deal = State()      # ввод ID сделки для привязки рейса
    msg_driver = State()     # ввод текста водителю


def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def url_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url)


BACK_MENU = [btn("◀️ Меню", "adm:menu")]


def menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📊 Сводка", "adm:sum")],
        [btn("🚛 В пути", "adm:trips:a:0"), btn("⏳ Без сделки", "adm:trips:u:0")],
        [btn("🔕 Молчат", "adm:trips:s:0"), btn("🏁 Близко к терминалу", "adm:trips:n:0")],
        [btn("👤 Водители", "adm:drv:0"), btn("🏭 Терминалы", "adm:term")],
        [btn("🔔 Уведомления", "adm:ntf")],
    ])


# ==================== ВСПОМОГАТЕЛЬНОЕ ====================

async def _trip_rows(session, kind: str):
    """Список (trip, driver, last_location) по виду: a — все в пути, u — без сделки,
    s — молчат дольше SILENCE_HOURS, n — ближе LAST_CALL_DISTANCE_KM к терминалу."""
    trips = await crud.list_active_trips(session, linked=False if kind == "u" else None)
    rows = []
    silence_border = datetime.utcnow() - timedelta(hours=settings.silence_hours)
    for t in trips:
        loc = await crud.get_last_trip_location(session, t)
        last_seen = loc.recorded_at if loc else t.started_at
        if kind == "s" and last_seen and last_seen > silence_border:
            continue
        if kind == "n":
            dist = loc.distance_to_destination_km if loc else None
            if dist is None or dist > settings.last_call_distance_km:
                continue
        driver = await crud.get_driver_by_id(session, t.driver_id)
        rows.append((t, driver, loc))
    if kind == "s":
        rows.sort(key=lambda r: (r[2].recorded_at if r[2] else r[0].started_at) or datetime.min)
    if kind == "n":
        rows.sort(key=lambda r: r[2].distance_to_destination_km)
    return rows


def _trip_short(t, loc) -> str:
    term = terminal_name(t.terminal_code).split(" — ")[0]
    seen = ago(loc.recorded_at) if loc else "нет точек"
    deal = f"#{t.bitrix_deal_id}" if t.bitrix_deal_id else "без сделки"
    return f"{t.truck_number} · {term} · {deal} · {seen}"[:60]


async def _summary_text(session) -> str:
    active = await crud.list_active_trips(session)
    linked = sum(1 for t in active if t.bitrix_deal_id)
    silent = await _trip_rows(session, "s")
    near = await _trip_rows(session, "n")
    drivers = await crud.list_drivers(session)
    blocked = sum(1 for d in drivers if not d.is_active)
    return (
        "📊 <b>Сводка</b>\n\n"
        f"🚛 В пути: <b>{len(active)}</b> (со сделкой {linked}, без сделки {len(active) - linked})\n"
        f"🔕 Молчат дольше {settings.silence_hours} ч: <b>{len(silent)}</b>\n"
        f"🏁 Ближе {settings.last_call_distance_km} км к терминалу: <b>{len(near)}</b>\n"
        f"👤 Водителей: {len(drivers)}" + (f", заблокировано {blocked}" if blocked else "")
    )


async def trip_card(session, trip_id: int):
    t = await crud.get_trip_by_id(session, trip_id)
    if not t:
        return "Рейс не найден.", InlineKeyboardMarkup(inline_keyboard=[BACK_MENU])
    driver = await crud.get_driver_by_id(session, t.driver_id)
    loc = await crud.get_last_trip_location(session, t)

    status = {"active": "в пути", "completed": "завершён", "cancelled": "отменён"}.get(t.status, t.status)
    lines = [
        f"🚛 <b>{escape(t.truck_number)}</b>" + (f" / {escape(t.trailer_number)}" if t.trailer_number else ""),
        f"👤 {driver_label(driver)}",
        f"📋 {deal_link(t.bitrix_deal_id, t.bitrix_deal_title)}",
        f"🏭 {escape(terminal_name(t.terminal_code))}",
        f"🕐 Рейс начат: {msk(t.started_at)} ({ago(t.started_at)}), статус: {status}",
    ]
    if t.shipment_date:
        days = (datetime.utcnow() - t.shipment_date).days
        lines.append(f"📦 Отгрузка: {msk(t.shipment_date, '%d.%m.%Y')} — в пути {days} дн.")
    if t.planned_arrival_date:
        lines.append(f"📅 План прибытия: {msk(t.planned_arrival_date, '%d.%m.%Y')}")
    if loc:
        dist = f", до терминала {loc.distance_to_destination_km:.0f} км" if loc.distance_to_destination_km else ""
        lines.append(f"📍 {escape(loc.address or '')}{dist}\n     {msk(loc.recorded_at)} ({ago(loc.recorded_at)})")
    else:
        lines.append("📍 Геопозиции ещё не было")
    if t.last_call_triggered:
        lines.append(f"🏁 Last call: {msk(t.last_call_date)}")

    kb: List[List[InlineKeyboardButton]] = []
    if t.status == "active":
        kb.append([btn("📍 Запросить геопозицию", f"adm:ask:{t.id}"), btn("✉️ Написать", f"adm:msg:{t.driver_id}")])
        if loc:
            kb.append([btn("🗺 Последняя точка", f"adm:pt:{t.id}")])
        if t.bitrix_deal_id:
            kb.append([url_btn("🔗 Открыть сделку", settings.deal_url(t.bitrix_deal_id)),
                       btn("🔁 Перепривязать", f"adm:bind:{t.id}")])
        else:
            kb.append([btn("🔍 Искать в Битриксе", f"adm:find:{t.id}"), btn("🔗 Привязать по ID", f"adm:bind:{t.id}")])
        kb.append([btn("🏁 Завершить рейс", f"adm:fin:{t.id}")])
    kb.append([btn("👤 Водитель", f"adm:d:{t.driver_id}")] + BACK_MENU)
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb)


async def driver_card(session, driver_id: int):
    d = await crud.get_driver_by_id(session, driver_id)
    if not d:
        return "Водитель не найден.", InlineKeyboardMarkup(inline_keyboard=[BACK_MENU])
    trips = await crud.list_driver_trips(session, d.id, limit=5)
    total = await crud.count_trips(session, d.id)
    last = await crud.get_last_location(session, d.id)
    lines = [
        f"👤 <b>{driver_label(d)}</b>",
        f"🆔 Telegram: <code>{d.telegram_id}</code>",
        f"🚛 Тягач: {escape(d.truck_number or '—')}",
        f"✅ Согласие: {msk(d.consent_date, '%d.%m.%Y') if d.consent_given else 'нет'}",
        f"📅 В боте с {msk(d.created_at, '%d.%m.%Y')}",
        f"📍 Последняя точка: {ago(last.recorded_at) if last else '—'}",
        "🚫 <b>Заблокирован</b>" if not d.is_active else "",
        f"\n<b>Рейсы ({total}):</b>",
    ]
    kb: List[List[InlineKeyboardButton]] = []
    for t in trips:
        mark = "🟢" if t.status == "active" else "⚪"
        deal = f"#{t.bitrix_deal_id}" if t.bitrix_deal_id else "без сделки"
        lines.append(f"{mark} {msk(t.started_at, '%d.%m.%Y')} {escape(t.truck_number)} · {deal} · "
                     f"{escape(terminal_name(t.terminal_code).split(' — ')[0])}")
        if t.status == "active":
            kb.append([btn(f"🚛 Активный рейс {t.truck_number}", f"adm:trip:{t.id}")])
    if not trips:
        lines.append("—")
    kb.append([btn("✉️ Написать", f"adm:msg:{d.id}"),
               btn("✅ Разблокировать" if not d.is_active else "🚫 Заблокировать", f"adm:blk:{d.id}")])
    kb.append([btn("◀️ Водители", "adm:drv:0")] + BACK_MENU)
    return "\n".join(x for x in lines if x != ""), InlineKeyboardMarkup(inline_keyboard=kb)


async def _edit(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        # «message is not modified» или старое сообщение — шлём новое
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)


# ==================== КОМАНДЫ ====================

@router.message(Command("myid"))
async def cmd_myid(message: Message):
    """Узнать свой Telegram ID (для добавления в ADMIN_IDS)"""
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


@router.message(Command("admin"), AdminFilter())
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    async with get_session() as session:
        text = await _summary_text(session)
    await message.answer(text + "\n\n🛠 <b>Админка</b>", reply_markup=menu_kb(), parse_mode="HTML")


@router.message(Command("cancel"), AdminFilter())
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=menu_kb())


# ==================== НАВИГАЦИЯ ====================

@router.callback_query(F.data == "adm:menu", AdminFilter())
async def cb_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    async with get_session() as session:
        text = await _summary_text(session)
    await _edit(cb, text + "\n\n🛠 <b>Админка</b>", menu_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:sum", AdminFilter())
async def cb_summary(cb: CallbackQuery):
    async with get_session() as session:
        text = await _summary_text(session)
    await _edit(cb, text, menu_kb())
    await cb.answer("Обновлено")


TRIP_LIST_TITLES = {
    "a": "🚛 Рейсы в пути",
    "u": "⏳ Рейсы без сделки",
    "s": "🔕 Молчат дольше {h} ч",
    "n": "🏁 Ближе {km} км к терминалу",
}


@router.callback_query(F.data.startswith("adm:trips:"), AdminFilter())
async def cb_trips(cb: CallbackQuery):
    _, _, kind, page = cb.data.split(":")
    page = int(page)
    async with get_session() as session:
        rows = await _trip_rows(session, kind)
    title = TRIP_LIST_TITLES[kind].format(h=settings.silence_hours, km=settings.last_call_distance_km)
    chunk = rows[page * PAGE:(page + 1) * PAGE]
    kb = [[btn(_trip_short(t, loc), f"adm:trip:{t.id}")] for t, _, loc in chunk]
    nav = []
    if page > 0:
        nav.append(btn("⬅️", f"adm:trips:{kind}:{page - 1}"))
    if (page + 1) * PAGE < len(rows):
        nav.append(btn("➡️", f"adm:trips:{kind}:{page + 1}"))
    if nav:
        kb.append(nav)
    kb.append(BACK_MENU)
    text = f"<b>{title}</b>: {len(rows)}" + ("" if rows else "\n\nПусто.")
    if rows:
        text += "\n<i>тягач · терминал · сделка · последняя точка</i>"
    await _edit(cb, text, InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:trip:"), AdminFilter())
async def cb_trip(cb: CallbackQuery):
    trip_id = int(cb.data.split(":")[2])
    async with get_session() as session:
        text, kb = await trip_card(session, trip_id)
    await _edit(cb, text, kb)
    await cb.answer()


# ==================== ДЕЙСТВИЯ С РЕЙСОМ ====================

@router.callback_query(F.data.startswith("adm:ask:"), AdminFilter())
async def cb_ask_location(cb: CallbackQuery):
    trip_id = int(cb.data.split(":")[2])
    async with get_session() as session:
        t = await crud.get_trip_by_id(session, trip_id)
        driver = await crud.get_driver_by_id(session, t.driver_id) if t else None
    if not driver:
        await cb.answer("Водитель не найден", show_alert=True)
        return
    try:
        await cb.bot.send_message(
            driver.telegram_id,
            "📍 Диспетчер просит отправить текущее местоположение.\n"
            "Нажмите кнопку «📍 Отправить местоположение» внизу.",
            reply_markup=keyboards.location_keyboard(),
        )
        await cb.answer("Запрос отправлен водителю", show_alert=True)
    except Exception as e:
        await cb.answer(f"Не отправлено: {e}"[:190], show_alert=True)


@router.callback_query(F.data.startswith("adm:pt:"), AdminFilter())
async def cb_last_point(cb: CallbackQuery):
    trip_id = int(cb.data.split(":")[2])
    async with get_session() as session:
        t = await crud.get_trip_by_id(session, trip_id)
        loc = await crud.get_last_trip_location(session, t) if t else None
    if not loc:
        await cb.answer("Точек нет", show_alert=True)
        return
    await cb.message.answer_location(latitude=loc.latitude, longitude=loc.longitude)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:find:"), AdminFilter())
async def cb_find_deal(cb: CallbackQuery):
    trip_id = int(cb.data.split(":")[2])
    async with get_session() as session:
        t = await crud.get_trip_by_id(session, trip_id)
        if not t:
            await cb.answer("Рейс не найден", show_alert=True)
            return
        try:
            deal = await bitrix_client.find_deal_by_truck_number(t.truck_number)
        except Exception as e:
            await cb.answer(f"Ошибка Битрикса: {e}"[:190], show_alert=True)
            return
        if not deal:
            await cb.answer(f"Открытой сделки с номером {t.truck_number} не найдено. "
                            f"Привяжите вручную по ID.", show_alert=True)
            return
        await _bind(cb.bot, session, t, deal)
        text, kb = await trip_card(session, trip_id)
    await _edit(cb, "✅ Сделка найдена и привязана.\n\n" + text, kb)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:bind:"), AdminFilter())
async def cb_bind_ask(cb: CallbackQuery, state: FSMContext):
    trip_id = int(cb.data.split(":")[2])
    await state.set_state(AdminStates.bind_deal)
    await state.update_data(trip_id=trip_id)
    await cb.message.answer("Введите ID сделки в Битрикс24 (число из адреса сделки).\n/cancel — отмена")
    await cb.answer()


@router.message(AdminStates.bind_deal, AdminFilter())
async def st_bind_deal(message: Message, state: FSMContext):
    text = (message.text or "").strip().lstrip("#")
    if not text.isdigit():
        await message.answer("Нужно число — ID сделки. /cancel — отмена")
        return
    data = await state.get_data()
    try:
        deal = await bitrix_client.get_deal(int(text))
    except Exception as e:
        await message.answer(f"Сделка {text} не найдена в Битриксе: {e}"[:300])
        return
    if not deal or not deal.get("ID"):
        await message.answer(f"Сделка {text} не найдена.")
        return
    async with get_session() as session:
        t = await crud.get_trip_by_id(session, data["trip_id"])
        if not t:
            await message.answer("Рейс не найден.")
            await state.clear()
            return
        await _bind(message.bot, session, t, deal)
        card, kb = await trip_card(session, t.id)
    await state.clear()
    await message.answer("✅ Рейс привязан к сделке.\n\n" + card, reply_markup=kb,
                         parse_mode="HTML", disable_web_page_preview=True)


async def _bind(bot, session, trip, deal: dict):
    """Привязать рейс к сделке: поля рейса, Telegram ID в сделку, комментарий, сообщение водителю."""
    apply_deal_to_trip(trip, deal)
    driver = await crud.get_driver_by_id(session, trip.driver_id)
    await session.flush()
    if driver:
        await crud.cancel_waiting_registrations(session, driver.telegram_id)
        await bitrix_client.update_driver_telegram_id(trip.bitrix_deal_id, driver.telegram_id, driver.username)
    await bitrix_client.add_timeline_comment(
        trip.bitrix_deal_id,
        f"🚛 Диспетчер привязал рейс {trip.truck_number} к сделке в Telegram-боте отслеживания.",
    )
    if driver:
        try:
            await bot.send_message(
                driver.telegram_id,
                f"✅ <b>Перевозка привязана к заказу</b>\n\n"
                f"📋 {escape(trip.bitrix_deal_title or '')}\n"
                f"🏭 Терминал: {escape(terminal_name(trip.terminal_code))}\n\n"
                f"Теперь ваше местоположение передаётся брокеру.",
                reply_markup=keyboards.location_keyboard(), parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Cannot notify driver about bind: {e}")


@router.callback_query(F.data.startswith("adm:fin:"), AdminFilter())
async def cb_finish_ask(cb: CallbackQuery):
    trip_id = int(cb.data.split(":")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        btn("✅ Да, завершить", f"adm:finok:{trip_id}"), btn("Отмена", f"adm:trip:{trip_id}"),
    ]])
    await _edit(cb, "Завершить рейс? Водитель получит сообщение, отслеживание остановится.", kb)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:finok:"), AdminFilter())
async def cb_finish(cb: CallbackQuery):
    trip_id = int(cb.data.split(":")[2])
    async with get_session() as session:
        t = await crud.get_trip_by_id(session, trip_id)
        if t and t.status == "active":
            await crud.complete_trip(session, t.id)
            driver = await crud.get_driver_by_id(session, t.driver_id)
            if t.bitrix_deal_id:
                await bitrix_client.add_timeline_comment(
                    t.bitrix_deal_id, "🏁 Диспетчер завершил отслеживание рейса в Telegram-боте.")
            if driver:
                try:
                    await cb.bot.send_message(
                        driver.telegram_id,
                        "✅ Перевозка завершена диспетчером. Отслеживание остановлено.\n"
                        "Для новой перевозки нажмите /start",
                        reply_markup=keyboards.remove_keyboard(),
                    )
                except Exception as e:
                    logger.warning(f"Cannot notify driver about finish: {e}")
        text, kb = await trip_card(session, trip_id)
    await _edit(cb, text, kb)
    await cb.answer("Рейс завершён")


# ==================== СООБЩЕНИЕ ВОДИТЕЛЮ ====================

@router.callback_query(F.data.startswith("adm:msg:"), AdminFilter())
async def cb_msg_ask(cb: CallbackQuery, state: FSMContext):
    driver_id = int(cb.data.split(":")[2])
    await state.set_state(AdminStates.msg_driver)
    await state.update_data(driver_id=driver_id)
    await cb.message.answer("Напишите сообщение водителю — отправлю от имени диспетчера.\n/cancel — отмена")
    await cb.answer()


@router.message(AdminStates.msg_driver, AdminFilter())
async def st_msg_driver(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пока можно отправить только текст. /cancel — отмена")
        return
    data = await state.get_data()
    async with get_session() as session:
        d = await crud.get_driver_by_id(session, data["driver_id"])
    await state.clear()
    if not d:
        await message.answer("Водитель не найден.")
        return
    try:
        await message.bot.send_message(d.telegram_id, f"✉️ <b>Сообщение от диспетчера:</b>\n\n{escape(message.text)}",
                                       parse_mode="HTML")
        await message.answer(f"✅ Отправлено: {driver_label(d)}", parse_mode="HTML", reply_markup=menu_kb())
    except Exception as e:
        await message.answer(f"Не отправлено: {e}"[:300])


# ==================== ВОДИТЕЛИ ====================

@router.callback_query(F.data.startswith("adm:drv:"), AdminFilter())
async def cb_drivers(cb: CallbackQuery):
    page = int(cb.data.split(":")[2])
    async with get_session() as session:
        drivers = await crud.list_drivers(session)
    chunk = drivers[page * PAGE:(page + 1) * PAGE]
    kb = []
    for d in chunk:
        name = " ".join(x for x in [d.first_name, d.last_name] if x) or (d.username or str(d.telegram_id))
        mark = "🚫 " if not d.is_active else ""
        kb.append([btn(f"{mark}{name} · {d.truck_number or '—'}"[:60], f"adm:d:{d.id}")])
    nav = []
    if page > 0:
        nav.append(btn("⬅️", f"adm:drv:{page - 1}"))
    if (page + 1) * PAGE < len(drivers):
        nav.append(btn("➡️", f"adm:drv:{page + 1}"))
    if nav:
        kb.append(nav)
    kb.append(BACK_MENU)
    await _edit(cb, f"👤 <b>Водители</b>: {len(drivers)}", InlineKeyboardMarkup(inline_keyboard=kb))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:d:"), AdminFilter())
async def cb_driver(cb: CallbackQuery):
    driver_id = int(cb.data.split(":")[2])
    async with get_session() as session:
        text, kb = await driver_card(session, driver_id)
    await _edit(cb, text, kb)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:blk:"), AdminFilter())
async def cb_block(cb: CallbackQuery):
    driver_id = int(cb.data.split(":")[2])
    async with get_session() as session:
        d = await crud.get_driver_by_id(session, driver_id)
        if d:
            d.is_active = not d.is_active
            await session.flush()
            note = "Разблокирован" if d.is_active else "Заблокирован"
        else:
            note = "Не найден"
        text, kb = await driver_card(session, driver_id)
    await _edit(cb, text, kb)
    await cb.answer(note)


# ==================== ТЕРМИНАЛЫ ====================

@router.callback_query(F.data == "adm:term", AdminFilter())
async def cb_terminals(cb: CallbackQuery):
    lines = ["🏭 <b>Терминалы</b> (ID из поля «Терминал» в Битриксе)\n"]
    missing = 0
    for tid, t in TERMINALS.items():
        ok = t.get("lat") and t.get("lon") and t.get("address_ru")
        if not ok:
            missing += 1
        lines.append(f"{'✅' if ok else '⚠️'} <code>{tid}</code> {escape(t.get('code', ''))}"
                     + ("" if ok else " — нет адреса/координат"))
    lines.append(f"\nБез адреса и координат: {missing}. Для них не считается расстояние "
                 f"и не срабатывает last call по расстоянию.")
    await _edit(cb, "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=[BACK_MENU]))
    await cb.answer()


# ==================== УВЕДОМЛЕНИЯ ====================

async def _ntf_kb(session) -> InlineKeyboardMarkup:
    kb = []
    for key, title in EVENT_TITLES.items():
        on = (await crud.get_setting(session, f"notify_{key}", "1")) == "1"
        kb.append([btn(f"{'🔔' if on else '🔕'} {title}", f"adm:ntf:{key}")])
    kb.append(BACK_MENU)
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "adm:ntf", AdminFilter())
async def cb_notify(cb: CallbackQuery):
    async with get_session() as session:
        kb = await _ntf_kb(session)
    await _edit(cb, "🔔 <b>Уведомления админам</b>\nНажмите, чтобы включить или выключить.\n"
                    "Настройка общая для всех админов.", kb)
    await cb.answer()


@router.callback_query(F.data.startswith("adm:ntf:"), AdminFilter())
async def cb_notify_toggle(cb: CallbackQuery):
    key = cb.data.split(":")[2]
    async with get_session() as session:
        on = (await crud.get_setting(session, f"notify_{key}", "1")) == "1"
        await crud.set_setting(session, f"notify_{key}", "0" if on else "1")
        kb = await _ntf_kb(session)
    await _edit(cb, "🔔 <b>Уведомления админам</b>\nНажмите, чтобы включить или выключить.\n"
                    "Настройка общая для всех админов.", kb)
    await cb.answer("Выключено" if on else "Включено")


# Кнопки админки у не-админа (например, после удаления из ADMIN_IDS)
@router.callback_query(F.data.startswith("adm:"))
async def cb_not_admin(cb: CallbackQuery):
    await cb.answer("Нет доступа", show_alert=True)


def trip_button(trip_id: int, text: str = "Открыть рейс") -> InlineKeyboardMarkup:
    """Кнопка для уведомлений админу."""
    return InlineKeyboardMarkup(inline_keyboard=[[btn(f"🚛 {text}", f"adm:trip:{trip_id}")]])


def driver_reply_button(driver_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[btn("✉️ Ответить", f"adm:msg:{driver_id}"),
                                                  btn("👤 Водитель", f"adm:d:{driver_id}")]])
