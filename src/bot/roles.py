"""
Роли: выбор роли при /start, регистрация клиента и брокера, приглашения,
«Мои рейсы» (карточка, где сейчас, история, карта маршрута),
создание рейса брокером/админом и подключение водителя по ссылке.
"""

from datetime import datetime
from html import escape
from typing import Optional

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import BaseFilter, Command, CommandObject, CommandStart
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
from src.services import access, events
from src.services.bitrix import bitrix_client
from src.services.notify import notify_admins
from src.services.trips import ago, apply_deal_to_trip, msk

settings = get_settings()
router = Router(name="roles")

_bot_username: Optional[str] = None


async def bot_username(bot) -> str:
    global _bot_username
    if not _bot_username:
        _bot_username = (await bot.get_me()).username
    return _bot_username


class RoleStates(StatesGroup):
    client_phone = State()
    client_inn = State()
    broker_phone = State()
    broker_company = State()
    new_trip_truck = State()
    new_trip_inn = State()
    write_dispatcher = State()


class ActiveParticipant(BaseFilter):
    """Активный клиент/брокер/менеджер из таблицы participants (не владелец и не водитель)."""

    def __init__(self, *roles: str):
        self.roles = roles

    async def __call__(self, event) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        async with get_session() as session:
            p = await access.get_participant(session, user.id)
        return bool(p and p.status == "active" and (not self.roles or p.role in self.roles))


class CanCreateTrip(BaseFilter):
    async def __call__(self, event) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        if access.is_admin(user.id):
            return True
        async with get_session() as session:
            p = await access.get_participant(session, user.id)
        return bool(p and p.status == "active" and p.role == "broker")


def menu_for(role: Optional[str]):
    if role in ("owner", "admin"):
        return keyboards.admin_menu()
    if role == "broker":
        return keyboards.broker_menu()
    if role == "client":
        return keyboards.client_menu()
    return None


def admin_pp_kb(pid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"adm:pp:ok:{pid}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:pp:no:{pid}"),
    ], [InlineKeyboardButton(text="👤 Карточка", callback_data=f"adm:p:{pid}")]])


# ==================== /start С ПРИГЛАШЕНИЕМ ====================

@router.message(CommandStart(deep_link=True))
async def start_with_link(message: Message, command: CommandObject, state: FSMContext):
    payload = (command.args or "").strip()
    if payload.startswith("inv_"):
        await _accept_role_invite(message, state, payload[4:])
    elif payload.startswith("drv_"):
        await _accept_driver_invite(message, state, payload[4:])
    else:
        raise SkipHandler()


async def _accept_role_invite(message: Message, state: FSMContext, code: str):
    await state.clear()
    async with get_session() as session:
        inv = await access.get_invite(session, code)
        if not inv or inv.kind not in ("broker", "admin"):
            await message.answer("Ссылка недействительна или уже использована. Попросите новую у диспетчера.")
            return
        u = message.from_user
        p = await access.upsert_participant(
            session, u.id, username=u.username, full_name=u.full_name, role=inv.kind, status="active",
        )
        inv.used_by = u.id
        inv.used_at = datetime.utcnow()
        if inv.kind == "admin":
            await access.reload_admins(session)
        pid = p.id
    title = access.ROLE_TITLES[inv.kind]
    await notify_admins("people", f"👤 По приглашению подключился <b>{escape(u.full_name)}</b> — {title}",
                        InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="👤 Карточка", callback_data=f"adm:p:{pid}")]]))
    if inv.kind == "admin":
        await message.answer("✅ Вы подключены как менеджер. Панель управления — /admin",
                             reply_markup=keyboards.admin_menu())
    else:
        await message.answer(
            "✅ Вы подключены как отправитель / брокер.\n\n"
            "«➕ Новый рейс» — создать рейс и получить ссылку для водителя.\n"
            "«📦 Мои рейсы» — где сейчас машины и их маршрут.",
            reply_markup=keyboards.broker_menu(),
        )


async def _accept_driver_invite(message: Message, state: FSMContext, code: str):
    from src.bot.handlers import send_consent_request
    async with get_session() as session:
        inv = await access.get_invite(session, code)
        trip = await crud.get_trip_by_id(session, inv.trip_id) if inv and inv.kind == "driver" else None
        if not trip or trip.status != "active":
            await message.answer("Ссылка недействительна или рейс уже завершён. Обратитесь к диспетчеру.")
            return
        u = message.from_user
        driver = await crud.get_driver_by_telegram_id(session, u.id)
        if not driver:
            driver = await crud.create_driver(session, telegram_id=u.id, username=u.username,
                                              first_name=u.first_name, last_name=u.last_name)
        if not driver.is_active:
            await message.answer("⛔ Доступ к боту закрыт. Обратитесь к диспетчеру.")
            return
        inv.used_by = u.id
        inv.used_at = datetime.utcnow()
        if driver.consent_given:
            await attach_driver(session, message.bot, driver, trip)
            text = await driver_trip_text(trip)
        else:
            text = None
        trip_id = trip.id
    if text:
        from src.bot.states import RegistrationStates
        await state.set_state(RegistrationStates.active_trip)
        await message.answer(text, reply_markup=keyboards.location_keyboard(), parse_mode="HTML")
    else:
        await state.update_data(invite_trip_id=trip_id)
        await send_consent_request(message, state)


async def driver_trip_text(trip) -> str:
    t = TERMINALS.get(str(trip.terminal_code or ""), {})
    return (
        f"✅ <b>Вы подключены к рейсу</b>\n\n"
        f"🚛 {escape(trip.truck_number)}\n"
        f"🏭 Терминал: {escape(terminal_name(trip.terminal_code))}\n"
        + (f"🏠 {escape(t['address_ru'])}\n" if t.get("address_ru") else "")
        + "\nНажмите «📍 Отправить местоположение»."
    )


async def attach_driver(session, bot, driver, trip):
    """Подключить водителя к рейсу (по ссылке или по совпадению номера)."""
    old = await crud.get_active_trip_by_driver(session, driver.id)
    if old and old.id != trip.id:
        await crud.complete_trip(session, old.id)
    first_driver = trip.driver_id is None
    trip.driver_id = driver.id
    driver.truck_number = trip.truck_number
    await session.flush()
    await crud.cancel_waiting_registrations(session, driver.telegram_id)
    if trip.bitrix_deal_id:
        await bitrix_client.update_driver_telegram_id(trip.bitrix_deal_id, driver.telegram_id, driver.username)
        await bitrix_client.add_timeline_comment(
            trip.bitrix_deal_id, f"🚛 Водитель подключился к рейсу {trip.truck_number} в Telegram-боте.")
    from src.services.trips import driver_label
    await notify_admins("match", f"🔗 <b>Водитель подключился к рейсу</b> {escape(trip.truck_number)}: "
                                 f"{driver_label(driver)}",
                        InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="🚛 Открыть рейс", callback_data=f"adm:trip:{trip.id}")]]))
    if first_driver:
        await events.on_trip_started(session, trip)


# ==================== /start БЕЗ ПРИГЛАШЕНИЯ ====================

@router.message(CommandStart())
async def start_by_role(message: Message, state: FSMContext):
    uid = message.from_user.id
    async with get_session() as session:
        p = await access.get_participant(session, uid)
        driver = await crud.get_driver_by_telegram_id(session, uid)
        n_trips = len(await access.trips_for_user(session, uid)) if (p or access.is_admin(uid)) else 0

    if access.is_admin(uid):
        await state.clear()
        await message.answer(
            f"🛠 <b>Вы админ.</b> Рейсов в работе и за 30 дней: {n_trips}.\n"
            f"/admin — панель управления, /driver — проверить бот глазами водителя.",
            reply_markup=keyboards.admin_menu(), parse_mode="HTML",
        )
        return
    if p:
        await state.clear()
        if p.status == "blocked":
            await message.answer("⛔ Доступ к боту закрыт. Обратитесь к диспетчеру.",
                                 reply_markup=keyboards.remove_keyboard())
        elif p.status == "pending":
            await message.answer("⏳ Ваша заявка на рассмотрении у диспетчера. Мы сообщим, когда доступ откроется.")
        else:
            who = escape(p.company_title or p.full_name or "")
            await message.answer(
                f"👋 Здравствуйте{', ' + who if who else ''}!\nРейсов: {n_trips}. «📦 Мои рейсы» — список.",
                reply_markup=menu_for(p.role),
            )
        return
    if driver:
        raise SkipHandler()  # обычный сценарий водителя
    await state.clear()
    await message.answer(
        "🚛 <b>Бот отслеживания грузов ГРАНИЦА 2004</b>\n\nКто вы?",
        reply_markup=keyboards.role_choice_keyboard(), parse_mode="HTML",
    )


@router.message(Command("driver"))
async def as_driver(message: Message, state: FSMContext):
    from src.bot.handlers import cmd_start
    await cmd_start(message, state)


@router.message(F.text == "🚛 Я водитель")
async def choose_driver(message: Message, state: FSMContext):
    from src.bot.handlers import cmd_start
    await cmd_start(message, state)


@router.message(F.text == "📦 Я получатель груза")
async def choose_client(message: Message, state: FSMContext):
    await state.set_state(RoleStates.client_phone)
    await message.answer(
        "Чтобы показать ваши грузы, поделитесь номером телефона — "
        "найдём вас в базе по номеру, который вы оставляли брокеру.",
        reply_markup=keyboards.phone_keyboard(),
    )


@router.message(F.text == "🌍 Я отправитель / брокер")
async def choose_broker(message: Message, state: FSMContext):
    await state.set_state(RoleStates.broker_phone)
    await message.answer("Поделитесь номером телефона для связи.", reply_markup=keyboards.phone_keyboard())


async def _cancel(message: Message, state: FSMContext) -> bool:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено. /start — начать заново.", reply_markup=keyboards.remove_keyboard())
        return True
    return False


def _own_contact(message: Message) -> Optional[str]:
    c = message.contact
    if not c or (c.user_id and c.user_id != message.from_user.id):
        return None
    return c.phone_number


# ==================== КЛИЕНТ ====================

@router.message(RoleStates.client_phone)
async def client_phone(message: Message, state: FSMContext):
    if await _cancel(message, state):
        return
    phone = _own_contact(message)
    if not phone:
        await message.answer("Нажмите кнопку «📱 Поделиться номером» — нужен ваш собственный номер.",
                             reply_markup=keyboards.phone_keyboard())
        return
    try:
        found = await bitrix_client.find_client_by_phone(phone)
    except Exception as e:
        logger.error(f"Bitrix phone lookup failed: {e}")
        found = None
    u = message.from_user
    if found:
        async with get_session() as session:
            p = await access.upsert_participant(
                session, u.id, username=u.username, full_name=u.full_name, phone=phone,
                role="client", status="active",
                bitrix_company_id=found["company_id"], bitrix_contact_id=found["contact_id"],
                company_title=found.get("company_title") or found.get("contact_name"),
            )
            trips = await access.trips_for_user(session, u.id)
            pid = p.id
        await state.clear()
        await notify_admins("people", f"👤 Новый клиент: <b>{escape(u.full_name)}</b> "
                                      f"({escape(found.get('company_title') or 'без компании')}), найден по телефону",
                            InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(text="👤 Карточка", callback_data=f"adm:p:{pid}")]]))
        await message.answer(
            f"✅ Нашли вас: <b>{escape(found.get('company_title') or found.get('contact_name') or '')}</b>.\n"
            f"Рейсов сейчас: {len(trips)}. Новые рейсы по вашим заказам появятся автоматически.",
            reply_markup=keyboards.client_menu(), parse_mode="HTML",
        )
        if trips:
            await send_trip_list(message, u.id)
        return
    await state.update_data(phone=phone)
    await state.set_state(RoleStates.client_inn)
    await message.answer("Не нашли этот номер в нашей базе. Введите ИНН вашей компании (10 или 12 цифр).",
                         reply_markup=keyboards.cancel_keyboard())


@router.message(RoleStates.client_inn)
async def client_inn(message: Message, state: FSMContext):
    if await _cancel(message, state):
        return
    inn = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if len(inn) not in (10, 12):
        await message.answer("ИНН — 10 или 12 цифр. Попробуйте ещё раз или нажмите «❌ Отмена».")
        return
    data = await state.get_data()
    try:
        company = await bitrix_client.find_company_by_inn(inn)
    except Exception as e:
        logger.error(f"Bitrix INN lookup failed: {e}")
        company = None
    u = message.from_user
    async with get_session() as session:
        p = await access.upsert_participant(
            session, u.id, username=u.username, full_name=u.full_name, phone=data.get("phone"),
            role="client", status="pending", inn=inn,
            bitrix_company_id=company["company_id"] if company else None,
            company_title=company["company_title"] if company else None,
        )
        pid = p.id
    await state.clear()
    if company:
        text = (f"🙋 <b>Клиент просит доступ</b>: {escape(u.full_name)}, тел. {escape(data.get('phone') or '—')}\n"
                f"ИНН {inn} → {escape(company['company_title'] or '')} (компания #{company['company_id']})\n"
                f"Телефона нет в Битриксе — проверьте, что это сотрудник компании.")
        kb = admin_pp_kb(pid)
    else:
        text = (f"🙋 <b>Клиент просит доступ</b>: {escape(u.full_name)}, тел. {escape(data.get('phone') or '—')}\n"
                f"ИНН {inn} в Битриксе не найден. Добавьте компанию или телефон контакта в Битрикс "
                f"и попросите клиента заново нажать /start.")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:pp:no:{pid}"),
            InlineKeyboardButton(text="✉️ Написать", callback_data=f"adm:pm:{pid}"),
        ]])
    await notify_admins("people", text, kb)
    await message.answer("⏳ Заявка отправлена диспетчеру. Мы сообщим, когда доступ откроется.",
                         reply_markup=keyboards.remove_keyboard())


# ==================== БРОКЕР ====================

@router.message(RoleStates.broker_phone)
async def broker_phone(message: Message, state: FSMContext):
    if await _cancel(message, state):
        return
    phone = _own_contact(message)
    if not phone:
        await message.answer("Нажмите кнопку «📱 Поделиться номером».", reply_markup=keyboards.phone_keyboard())
        return
    await state.update_data(phone=phone)
    await state.set_state(RoleStates.broker_company)
    await message.answer("Напишите название вашей компании и страну (например: «Sugd Logistics, Таджикистан»).",
                         reply_markup=keyboards.cancel_keyboard())


@router.message(RoleStates.broker_company)
async def broker_company(message: Message, state: FSMContext):
    if await _cancel(message, state):
        return
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Напишите название компании текстом.")
        return
    data = await state.get_data()
    u = message.from_user
    async with get_session() as session:
        p = await access.upsert_participant(
            session, u.id, username=u.username, full_name=u.full_name, phone=data.get("phone"),
            role="broker", status="pending", company_title=message.text.strip()[:300],
        )
        pid = p.id
    await state.clear()
    await notify_admins(
        "people",
        f"🙋 <b>Брокер / отправитель просит доступ</b>: {escape(u.full_name)}"
        + (f" @{escape(u.username)}" if u.username else "")
        + f"\n📞 {escape(data.get('phone') or '—')}\n🏢 {escape(message.text.strip())}",
        admin_pp_kb(pid),
    )
    await message.answer("⏳ Заявка отправлена диспетчеру. Мы сообщим, когда доступ откроется.",
                         reply_markup=keyboards.remove_keyboard())


# ==================== МОИ РЕЙСЫ ====================

def _trip_line(t, loc) -> str:
    mark = "🟢" if t.status == "active" else "⚪"
    seen = ago(loc.recorded_at) if loc else "нет точек"
    return f"{mark} {t.truck_number} → {terminal_name(t.terminal_code).split(' — ')[0]} · {seen}"[:60]


async def send_trip_list(message: Message, user_id: int):
    async with get_session() as session:
        trips = await access.trips_for_user(session, user_id)
        rows = [(t, await crud.get_last_trip_location(session, t)) for t in trips]
    if not rows:
        await message.answer("Рейсов пока нет. Когда по вашему заказу поедет машина, она появится здесь.")
        return
    kb = [[InlineKeyboardButton(text=_trip_line(t, loc), callback_data=f"v:t:{t.id}")] for t, loc in rows]
    await message.answer(
        f"📦 <b>Рейсы</b> ({len(rows)}): 🟢 в пути, ⚪ завершён за последние 30 дней",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML",
    )


@router.message(F.text.in_({"📦 Мои рейсы", "📦 Все рейсы"}))
async def my_trips(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not access.is_admin(uid):
        async with get_session() as session:
            p = await access.get_participant(session, uid)
        if not p or p.status != "active":
            raise SkipHandler()
    await state.clear()
    await send_trip_list(message, uid)


async def viewer_card(session, trip, user_id: int):
    loc = await crud.get_last_trip_location(session, trip)
    t = TERMINALS.get(str(trip.terminal_code or ""), {})
    status = {"active": "🟢 в пути", "completed": "⚪ завершён", "cancelled": "отменён"}.get(trip.status, trip.status)
    lines = [
        f"🚛 <b>{escape(trip.truck_number)}</b> — {status}",
    ]
    if trip.bitrix_deal_title:
        lines.append(f"📋 {escape(trip.bitrix_deal_title)}")
    lines.append(f"🏭 {escape(terminal_name(trip.terminal_code))}")
    if t.get("address_ru"):
        lines.append(f"     {escape(t['address_ru'])}")
    if trip.shipment_date:
        lines.append(f"📦 Отгрузка: {msk(trip.shipment_date, '%d.%m.%Y')}")
    if trip.planned_arrival_date:
        lines.append(f"📅 План прибытия: {msk(trip.planned_arrival_date, '%d.%m.%Y')}")
    if not trip.driver_id:
        lines.append("👤 Водитель ещё не подключился")
    if loc:
        dist = f"\n📏 До терминала: {loc.distance_to_destination_km:.0f} км" if loc.distance_to_destination_km else ""
        lines.append(f"📍 <b>Сейчас:</b> {escape(loc.address or '')}\n🕐 {msk(loc.recorded_at)} МСК "
                     f"({ago(loc.recorded_at)}){dist}")
        lines.append(f"🌐 {loc.latitude:.5f}, {loc.longitude:.5f}")
    else:
        lines.append("📍 Местоположение ещё не передавалось")
    if trip.arrived_notified_at:
        lines.append(f"🏁 У терминала с {msk(trip.arrived_notified_at)}")

    kb = []
    if loc:
        kb.append([InlineKeyboardButton(text="📍 Где сейчас", callback_data=f"v:loc:{trip.id}"),
                   InlineKeyboardButton(text="📜 История", callback_data=f"v:h:{trip.id}")])
        url = access.track_url(trip.id)
        if url:
            kb.append([InlineKeyboardButton(text="🗺 Маршрут на карте", url=url)])
    kb.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=f"v:t:{trip.id}"),
               InlineKeyboardButton(text="◀️ Все рейсы", callback_data="v:list")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb)


async def _load_viewable(cb: CallbackQuery, trip_id: int):
    async with get_session() as session:
        trip = await crud.get_trip_by_id(session, trip_id)
        ok = await access.can_view(session, cb.from_user.id, trip)
    if not ok:
        await cb.answer("Нет доступа к этому рейсу", show_alert=True)
        return None
    return trip


@router.callback_query(F.data == "v:list")
async def cb_list(cb: CallbackQuery):
    await send_trip_list(cb.message, cb.from_user.id)
    await cb.answer()


@router.callback_query(F.data.startswith("v:t:"))
async def cb_card(cb: CallbackQuery):
    trip_id = int(cb.data.split(":")[2])
    if not await _load_viewable(cb, trip_id):
        return
    async with get_session() as session:
        trip = await crud.get_trip_by_id(session, trip_id)
        text, kb = await viewer_card(session, trip, cb.from_user.id)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()


@router.callback_query(F.data.startswith("v:loc:"))
async def cb_where(cb: CallbackQuery):
    trip_id = int(cb.data.split(":")[2])
    trip = await _load_viewable(cb, trip_id)
    if not trip:
        return
    async with get_session() as session:
        loc = await crud.get_last_trip_location(session, trip)
    if not loc:
        await cb.answer("Точек ещё нет", show_alert=True)
        return
    await cb.message.answer_location(latitude=loc.latitude, longitude=loc.longitude)
    await cb.answer(f"Точка {ago(loc.recorded_at)}")


@router.callback_query(F.data.startswith("v:h:"))
async def cb_history(cb: CallbackQuery):
    trip_id = int(cb.data.split(":")[2])
    trip = await _load_viewable(cb, trip_id)
    if not trip:
        return
    async with get_session() as session:
        points = await crud.get_trip_points(session, trip)
    if not points:
        await cb.answer("Точек ещё нет", show_alert=True)
        return
    last = points[-15:]
    lines = [f"📜 <b>История {escape(trip.truck_number)}</b> — точек всего {len(points)}, последние {len(last)}:\n"]
    for p in reversed(last):
        addr = ", ".join((p.address or "").split(", ")[:3])
        dist = f" · {p.distance_to_destination_km:.0f} км до терминала" if p.distance_to_destination_km else ""
        lines.append(f"🕐 {msk(p.recorded_at)} — {escape(addr)}{dist}")
    url = access.track_url(trip.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗺 Маршрут на карте", url=url)]]) if url else None
    await cb.message.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()


# ==================== НОВЫЙ РЕЙС (брокер / админ) ====================

@router.message(F.text == "➕ Новый рейс", CanCreateTrip())
async def new_trip_start(message: Message, state: FSMContext):
    await state.set_state(RoleStates.new_trip_truck)
    await message.answer("Введите номер тягача (или контейнера), без пробелов:", reply_markup=keyboards.cancel_keyboard())


@router.message(RoleStates.new_trip_truck)
async def new_trip_truck(message: Message, state: FSMContext):
    if await _cancel(message, state):
        return
    from src.bot.handlers import validate_plate_number
    truck = (message.text or "").strip().upper().replace(" ", "").replace("-", "")
    if not validate_plate_number(truck):
        await message.answer("Неверный формат номера. Пример: 01A123BC, А123ВС77, TPPU4000202")
        return
    await state.update_data(truck=truck)
    await state.set_state(RoleStates.new_trip_inn)
    await message.answer("ИНН получателя в России (10 или 12 цифр) — или «Пропустить»:",
                         reply_markup=keyboards.skip_keyboard())


@router.message(RoleStates.new_trip_inn)
async def new_trip_inn(message: Message, state: FSMContext):
    if await _cancel(message, state):
        return
    text = (message.text or "").strip()
    inn = "".join(ch for ch in text if ch.isdigit())
    if text != "Пропустить" and len(inn) not in (10, 12):
        await message.answer("ИНН — 10 или 12 цифр, или нажмите «Пропустить».")
        return
    data = await state.get_data()
    truck = data["truck"]
    u = message.from_user

    deal = None
    try:
        deal = await bitrix_client.find_deal_by_truck_number(truck)
    except Exception as e:
        logger.error(f"Bitrix search failed: {e}")
    company = None
    if inn and not deal:
        try:
            company = await bitrix_client.find_company_by_inn(inn)
        except Exception as e:
            logger.error(f"Bitrix INN lookup failed: {e}")

    async with get_session() as session:
        p = await access.get_participant(session, u.id)
        trip = await crud.create_trip(
            session, driver_id=None, truck_number=truck,
            created_by_participant_id=p.id if p else None,
        )
        if deal:
            apply_deal_to_trip(trip, deal)
        elif company:
            trip.bitrix_company_id = company["company_id"]
        inv = await access.create_invite(session, "driver", u.id, trip_id=trip.id, days=30)
        trip_id, deal_id, deal_title = trip.id, trip.bitrix_deal_id, trip.bitrix_deal_title
        tname = terminal_name(trip.terminal_code)
    await state.clear()

    link = access.invite_link(await bot_username(message.bot), "drv", inv.code)
    role = "admin" if access.is_admin(u.id) else "broker"
    lines = [f"✅ <b>Рейс {escape(truck)} создан</b>"]
    if deal_id:
        lines.append(f"📋 Найдена сделка: {escape(deal_title or '')}\n🏭 {escape(tname)}")
    else:
        lines.append("Сделка с этим номером пока не найдена — диспетчер привяжет её.")
    lines.append(f"\n👉 <b>Перешлите водителю ссылку:</b>\n{link}\n\n"
                 f"Водитель откроет её, даст согласие — и сразу окажется в этом рейсе, номер вводить не нужно.")
    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True,
                         reply_markup=menu_for(role))
    if role == "broker":
        await notify_admins(
            "reg", f"➕ <b>Брокер {escape(u.full_name)} создал рейс</b> {escape(truck)}"
                   + (f"\n📋 сделка #{deal_id}" if deal_id else "\n⚠️ сделка не найдена"),
            InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🚛 Открыть рейс", callback_data=f"adm:trip:{trip_id}")]]),
        )


# ==================== НАПИСАТЬ ДИСПЕТЧЕРУ ====================

@router.message(F.text == "✉️ Написать диспетчеру", ActiveParticipant("client", "broker"))
async def write_dispatcher(message: Message, state: FSMContext):
    await state.set_state(RoleStates.write_dispatcher)
    await message.answer("Напишите сообщение — передам диспетчеру.", reply_markup=keyboards.cancel_keyboard())


@router.message(RoleStates.write_dispatcher)
async def write_dispatcher_text(message: Message, state: FSMContext):
    if await _cancel(message, state):
        return
    if not message.text:
        await message.answer("Пока можно отправить только текст.")
        return
    await _forward_participant_text(message, state)


@router.message(F.text & ~F.text.startswith("/"), ActiveParticipant("client", "broker"))
async def participant_free_text(message: Message, state: FSMContext):
    await _forward_participant_text(message, state)


async def _forward_participant_text(message: Message, state: FSMContext):
    async with get_session() as session:
        p = await access.get_participant(session, message.from_user.id)
    await state.clear()
    role = access.ROLE_TITLES.get(p.role, p.role)
    who = escape(p.full_name or "") + (f" ({escape(p.company_title)})" if p.company_title else "")
    await notify_admins(
        "people", f"💬 <b>Сообщение</b> от {role}: {who}\n\n{escape(message.text)}",
        InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✉️ Ответить", callback_data=f"adm:pm:{p.id}"),
            InlineKeyboardButton(text="👤 Карточка", callback_data=f"adm:p:{p.id}"),
        ]]),
    )
    await message.answer("✉️ Сообщение передано диспетчеру.", reply_markup=menu_for(p.role))
