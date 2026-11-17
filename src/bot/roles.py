"""
Роли: выбор языка и роли при /start, регистрация клиента и брокера, приглашения,
«Мои рейсы» (карточка, где сейчас, история, карта маршрута),
создание рейса брокером/админом и подключение водителя по ссылке.
Тексты — на языке пользователя (src/i18n.py); уведомления админам — на русском.
"""

from datetime import datetime
from html import escape
from typing import Optional

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import BaseFilter, Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

from src import i18n
from src.bot import keyboards
from src.config import get_settings
from src.db import crud
from src.db.database import get_session
from src.i18n import V, t
from src.services import access, events
from src.services.bitrix import bitrix_client
from src.services.deal_sync import announce_link
from src.services.notify import notify_admins
from src.services.trips import apply_deal_to_trip, msk

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


def menu_for(role: Optional[str], lang: str = "ru"):
    if role in ("owner", "admin"):
        return keyboards.admin_menu()
    if role == "broker":
        return keyboards.broker_menu(lang)
    if role == "client":
        return keyboards.client_menu(lang)
    return None


def admin_pp_kb(pid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"adm:pp:ok:{pid}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:pp:no:{pid}"),
    ], [InlineKeyboardButton(text="👤 Карточка", callback_data=f"adm:p:{pid}")]])


def _card_kb(pid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👤 Карточка", callback_data=f"adm:p:{pid}")]])


# ==================== ЯЗЫК ====================

@router.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext):
    await message.answer(t("ru", "lang_choose"), reply_markup=keyboards.language_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def cb_language(cb: CallbackQuery, state: FSMContext):
    lang = i18n.norm(cb.data.split(":")[1])
    await i18n.set_lang(cb.from_user.id, lang)
    await cb.answer(t(lang, "lang_set"))
    try:
        await cb.message.edit_text(t(lang, "lang_set"))
    except Exception:
        pass
    await state.clear()
    await run_start(cb.message, state, lang, cb.from_user)


# ==================== /start С ПРИГЛАШЕНИЕМ ====================

@router.message(CommandStart(deep_link=True))
async def start_with_link(message: Message, command: CommandObject, state: FSMContext, lang: str = "ru"):
    payload = (command.args or "").strip()
    if payload.startswith("inv_"):
        await _accept_role_invite(message, state, payload[4:], lang)
    elif payload.startswith("drv_"):
        await _accept_driver_invite(message, state, payload[4:], lang)
    else:
        raise SkipHandler()


async def _accept_role_invite(message: Message, state: FSMContext, code: str, lang: str):
    await state.clear()
    async with get_session() as session:
        inv = await access.get_invite(session, code)
        if not inv or inv.kind not in ("broker", "admin"):
            await message.answer(t(lang, "invite_invalid"))
            return
        u = message.from_user
        p = await access.upsert_participant(
            session, u.id, username=u.username, full_name=u.full_name, role=inv.kind, status="active",
        )
        inv.used_by = u.id
        inv.used_at = datetime.utcnow()
        if inv.kind == "admin":
            await access.reload_admins(session)
        pid, kind = p.id, inv.kind
    await notify_admins("people", f"👤 По приглашению подключился <b>{escape(u.full_name)}</b> — "
                                  f"{access.ROLE_TITLES[kind]}", _card_kb(pid))
    if kind == "admin":
        await message.answer(t(lang, "joined_manager"), reply_markup=keyboards.admin_menu())
    else:
        await message.answer(
            t(lang, "joined_broker", new=t(lang, "btn_create_trip"), my=t(lang, "btn_my_trips"))
            + "\n\n" + t(lang, "lang_hint"),
            reply_markup=keyboards.broker_menu(lang),
        )


async def _accept_driver_invite(message: Message, state: FSMContext, code: str, lang: str):
    from src.bot.handlers import send_consent_request
    from src.bot.states import RegistrationStates
    async with get_session() as session:
        inv = await access.get_invite(session, code)
        trip = await crud.get_trip_by_id(session, inv.trip_id) if inv and inv.kind == "driver" else None
        if not trip or trip.status != "active":
            await message.answer(t(lang, "invite_invalid_driver"))
            return
        u = message.from_user
        driver = await crud.get_driver_by_telegram_id(session, u.id)
        if not driver:
            driver = await crud.create_driver(session, telegram_id=u.id, username=u.username,
                                              first_name=u.first_name, last_name=u.last_name)
        if not driver.is_active:
            await message.answer(t(lang, "blocked"))
            return
        inv.used_by = u.id
        inv.used_at = datetime.utcnow()
        text = None
        if driver.consent_given:
            await attach_driver(session, message.bot, driver, trip, how="водитель открыл ссылку-приглашение")
            text = driver_trip_text(lang, trip)
        trip_id = trip.id
    if text:
        await state.set_state(RegistrationStates.active_trip)
        await message.answer(text, reply_markup=keyboards.location_keyboard(lang), parse_mode="HTML")
    else:
        await state.update_data(invite_trip_id=trip_id)
        await send_consent_request(message, state, lang)
        await message.answer(t(lang, "lang_hint"))


def driver_trip_text(lang: str, trip) -> str:
    addr = i18n.terminal_address(lang, trip.terminal_code)
    return t(lang, "attached_to_trip", truck=escape(trip.truck_number),
             terminal=escape(i18n.terminal_name(lang, trip.terminal_code)),
             address=(f"🏠 {escape(addr)}\n" if addr else ""), btn=t(lang, "btn_send_location"))


async def attach_driver(session, bot, driver, trip, how: str = "водитель подключился к рейсу"):
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
        await announce_link(session, trip, driver, how)
    from src.services.trips import driver_label
    await notify_admins("match", f"🔗 <b>Водитель подключился к рейсу</b> {escape(trip.truck_number)}: "
                                 f"{driver_label(driver)}",
                        InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="🚛 Открыть рейс", callback_data=f"adm:trip:{trip.id}")]]))
    if first_driver:
        await events.on_trip_started(session, trip)


# ==================== /start БЕЗ ПРИГЛАШЕНИЯ ====================

@router.message(CommandStart())
async def start_by_role(message: Message, state: FSMContext, lang: str = "ru"):
    if await i18n.stored_lang(message.from_user.id) is None:
        await state.clear()
        await message.answer(t(lang, "lang_choose"), reply_markup=keyboards.language_keyboard())
        return
    await run_start(message, state, lang, message.from_user)


async def run_start(message: Message, state: FSMContext, lang: str, user):
    """Приветствие по роли. message — куда отвечать, user — кто нажал."""
    uid = user.id
    async with get_session() as session:
        p = await access.get_participant(session, uid)
        driver = await crud.get_driver_by_telegram_id(session, uid)
        n_trips = len(await access.trips_for_user(session, uid)) if (p or access.is_admin(uid)) else 0

    if access.is_admin(uid):
        await state.clear()
        await message.answer(
            f"🛠 <b>Вы админ.</b> Рейсов в работе и за 30 дней: {n_trips}.\n"
            f"/admin — панель управления, /driver — проверить бот глазами водителя, /language — язык.",
            reply_markup=keyboards.admin_menu(), parse_mode="HTML",
        )
        return
    if p:
        await state.clear()
        if p.status == "blocked":
            await message.answer(t(lang, "blocked"), reply_markup=keyboards.remove_keyboard())
        elif p.status == "pending":
            await message.answer(t(lang, "pending_wait"))
        else:
            who = escape(p.company_title or p.full_name or "")
            await message.answer(
                t(lang, "greet", who=(", " + who) if who else "", n=n_trips, my=t(lang, "btn_my_trips")),
                reply_markup=menu_for(p.role, lang),
            )
        return
    if driver:
        from src.bot.handlers import cmd_start
        await cmd_start(message, state, lang, user=user)
        return
    await state.clear()
    await message.answer(t(lang, "who_are_you"), reply_markup=keyboards.role_choice_keyboard(lang), parse_mode="HTML")


@router.message(Command("driver"))
async def as_driver(message: Message, state: FSMContext, lang: str = "ru"):
    from src.bot.handlers import cmd_start
    await cmd_start(message, state, lang)


@router.message(F.text.in_(V("btn_role_driver")))
async def choose_driver(message: Message, state: FSMContext, lang: str = "ru"):
    from src.bot.handlers import cmd_start
    await cmd_start(message, state, lang)


@router.message(F.text.in_(V("btn_role_client")))
async def choose_client(message: Message, state: FSMContext, lang: str = "ru"):
    await state.set_state(RoleStates.client_phone)
    await message.answer(t(lang, "client_phone_ask"), reply_markup=keyboards.phone_keyboard(lang))


@router.message(F.text.in_(V("btn_role_broker")))
async def choose_broker(message: Message, state: FSMContext, lang: str = "ru"):
    await state.set_state(RoleStates.broker_phone)
    await message.answer(t(lang, "broker_phone_ask"), reply_markup=keyboards.phone_keyboard(lang))


async def _cancel(message: Message, state: FSMContext, lang: str) -> bool:
    if message.text in V("btn_cancel"):
        await state.clear()
        await message.answer(t(lang, "cancelled"), reply_markup=keyboards.remove_keyboard())
        return True
    return False


def _own_contact(message: Message) -> Optional[str]:
    c = message.contact
    if not c or (c.user_id and c.user_id != message.from_user.id):
        return None
    return c.phone_number


# ==================== КЛИЕНТ ====================

@router.message(RoleStates.client_phone)
async def client_phone(message: Message, state: FSMContext, lang: str = "ru"):
    if await _cancel(message, state, lang):
        return
    phone = _own_contact(message)
    if not phone:
        await message.answer(t(lang, "need_own_phone", btn=t(lang, "btn_share_phone")),
                             reply_markup=keyboards.phone_keyboard(lang))
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
                            _card_kb(pid))
        await message.answer(
            t(lang, "client_found", name=escape(found.get("company_title") or found.get("contact_name") or ""),
              n=len(trips)),
            reply_markup=keyboards.client_menu(lang), parse_mode="HTML",
        )
        if trips:
            await send_trip_list(message, u.id, lang)
        return
    await state.update_data(phone=phone)
    await state.set_state(RoleStates.client_inn)
    await message.answer(t(lang, "client_inn_ask"), reply_markup=keyboards.cancel_keyboard(lang))


@router.message(RoleStates.client_inn)
async def client_inn(message: Message, state: FSMContext, lang: str = "ru"):
    if await _cancel(message, state, lang):
        return
    inn = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if len(inn) not in (10, 12):
        await message.answer(t(lang, "inn_bad", btn=t(lang, "btn_cancel")))
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
    await message.answer(t(lang, "request_sent"), reply_markup=keyboards.remove_keyboard())


# ==================== БРОКЕР ====================

@router.message(RoleStates.broker_phone)
async def broker_phone(message: Message, state: FSMContext, lang: str = "ru"):
    if await _cancel(message, state, lang):
        return
    phone = _own_contact(message)
    if not phone:
        await message.answer(t(lang, "need_own_phone", btn=t(lang, "btn_share_phone")),
                             reply_markup=keyboards.phone_keyboard(lang))
        return
    await state.update_data(phone=phone)
    await state.set_state(RoleStates.broker_company)
    await message.answer(t(lang, "broker_company_ask"), reply_markup=keyboards.cancel_keyboard(lang))


@router.message(RoleStates.broker_company)
async def broker_company(message: Message, state: FSMContext, lang: str = "ru"):
    if await _cancel(message, state, lang):
        return
    if not message.text or len(message.text.strip()) < 2:
        await message.answer(t(lang, "company_text_needed"))
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
        + f"\n📞 {escape(data.get('phone') or '—')}\n🏢 {escape(message.text.strip())}"
        + f"\n🌐 Язык: {i18n.LANG_NAMES[lang]}",
        admin_pp_kb(pid),
    )
    await message.answer(t(lang, "request_sent"), reply_markup=keyboards.remove_keyboard())


# ==================== МОИ РЕЙСЫ ====================

def _trip_line(lang, trip, loc) -> str:
    mark = "🟢" if trip.status == "active" else "⚪"
    seen = i18n.ago(lang, loc.recorded_at) if loc else t(lang, "no_points_short")
    return f"{mark} {trip.truck_number} → {i18n.terminal_short(lang, trip.terminal_code)} · {seen}"[:60]


async def send_trip_list(message: Message, user_id: int, lang: str = "ru"):
    async with get_session() as session:
        trips = await access.trips_for_user(session, user_id)
        rows = [(tr, await crud.get_last_trip_location(session, tr)) for tr in trips]
    if not rows:
        await message.answer(t(lang, "no_trips"))
        return
    kb = [[InlineKeyboardButton(text=_trip_line(lang, tr, loc), callback_data=f"v:t:{tr.id}")] for tr, loc in rows]
    await message.answer(t(lang, "trips_header", n=len(rows)),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")


@router.message(F.text.in_(V("btn_my_trips") | {"📦 Все рейсы"}))
async def my_trips(message: Message, state: FSMContext, lang: str = "ru"):
    uid = message.from_user.id
    if not access.is_admin(uid):
        async with get_session() as session:
            p = await access.get_participant(session, uid)
        if not p or p.status != "active":
            raise SkipHandler()
    await state.clear()
    await send_trip_list(message, uid, lang)


async def viewer_card(session, trip, lang: str = "ru"):
    loc = await crud.get_last_trip_location(session, trip)
    status = {"active": t(lang, "st_active"), "completed": t(lang, "st_done"),
              "cancelled": t(lang, "st_cancelled")}.get(trip.status, trip.status)
    lines = [f"🚛 <b>{escape(trip.truck_number)}</b> — {status}"]
    if trip.bitrix_deal_title:
        lines.append(f"📋 {escape(trip.bitrix_deal_title)}")
    lines.append(f"🏭 {escape(i18n.terminal_name(lang, trip.terminal_code))}")
    addr = i18n.terminal_address(lang, trip.terminal_code)
    if addr:
        lines.append(f"     {escape(addr)}")
    if trip.shipment_date:
        lines.append(t(lang, "card_shipment", d=msk(trip.shipment_date, "%d.%m.%Y")))
    if trip.planned_arrival_date:
        lines.append(t(lang, "card_planned", d=msk(trip.planned_arrival_date, "%d.%m.%Y")))
    if not trip.driver_id:
        lines.append(t(lang, "card_no_driver"))
    if loc:
        dist = t(lang, "card_dist", km=f"{loc.distance_to_destination_km:.0f}") if loc.distance_to_destination_km else ""
        lines.append(t(lang, "card_now", addr=escape(loc.address or ""),
                       time=f"{msk(loc.recorded_at)} {t(lang, 'msk')}", ago=i18n.ago(lang, loc.recorded_at)) + dist)
        lines.append(f"🌐 {loc.latitude:.5f}, {loc.longitude:.5f}")
    else:
        lines.append(t(lang, "card_no_location"))
    if trip.arrived_notified_at:
        lines.append(t(lang, "card_at_terminal", t=msk(trip.arrived_notified_at)))

    kb = []
    if loc:
        kb.append([InlineKeyboardButton(text=t(lang, "btn_where"), callback_data=f"v:loc:{trip.id}"),
                   InlineKeyboardButton(text=t(lang, "btn_history"), callback_data=f"v:h:{trip.id}")])
        url = access.track_url(trip.id)
        if url:
            kb.append([InlineKeyboardButton(text=t(lang, "btn_map"), url=url)])
    if trip.bitrix_deal_id:
        kb.append([InlineKeyboardButton(text=t(lang, "btn_deal"), callback_data=f"d:{trip.bitrix_deal_id}")])
    kb.append([InlineKeyboardButton(text=t(lang, "btn_refresh"), callback_data=f"v:t:{trip.id}"),
               InlineKeyboardButton(text=t(lang, "btn_all_trips"), callback_data="v:list")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb)


async def _load_viewable(cb: CallbackQuery, trip_id: int, lang: str):
    async with get_session() as session:
        trip = await crud.get_trip_by_id(session, trip_id)
        ok = await access.can_view(session, cb.from_user.id, trip)
    if not ok:
        await cb.answer(t(lang, "no_access_trip"), show_alert=True)
        return None
    return trip


@router.callback_query(F.data == "v:list")
async def cb_list(cb: CallbackQuery, lang: str = "ru"):
    await send_trip_list(cb.message, cb.from_user.id, lang)
    await cb.answer()


@router.callback_query(F.data.startswith("v:t:"))
async def cb_card(cb: CallbackQuery, lang: str = "ru"):
    trip_id = int(cb.data.split(":")[2])
    if not await _load_viewable(cb, trip_id, lang):
        return
    async with get_session() as session:
        trip = await crud.get_trip_by_id(session, trip_id)
        text, kb = await viewer_card(session, trip, lang)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()


@router.callback_query(F.data.startswith("v:loc:"))
async def cb_where(cb: CallbackQuery, lang: str = "ru"):
    trip = await _load_viewable(cb, int(cb.data.split(":")[2]), lang)
    if not trip:
        return
    async with get_session() as session:
        loc = await crud.get_last_trip_location(session, trip)
    if not loc:
        await cb.answer(t(lang, "no_points"), show_alert=True)
        return
    await cb.message.answer_location(latitude=loc.latitude, longitude=loc.longitude)
    await cb.answer(t(lang, "point_ago", ago=i18n.ago(lang, loc.recorded_at)))


@router.callback_query(F.data.startswith("v:h:"))
async def cb_history(cb: CallbackQuery, lang: str = "ru"):
    trip = await _load_viewable(cb, int(cb.data.split(":")[2]), lang)
    if not trip:
        return
    async with get_session() as session:
        points = await crud.get_trip_points(session, trip)
    if not points:
        await cb.answer(t(lang, "no_points"), show_alert=True)
        return
    last = points[-15:]
    lines = [t(lang, "history_header", truck=escape(trip.truck_number), n=len(points), k=len(last))]
    for p in reversed(last):
        addr = ", ".join((p.address or "").split(", ")[:3])
        dist = t(lang, "history_dist", km=f"{p.distance_to_destination_km:.0f}") if p.distance_to_destination_km else ""
        lines.append(f"🕐 {msk(p.recorded_at)} — {escape(addr)}{dist}")
    url = access.track_url(trip.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_map"), url=url)]]) if url else None
    await cb.message.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()


# ==================== МОИ СДЕЛКИ ====================

async def _deals_for(session, user_id: int):
    """[(deal_id, title, stage_id)] — клиенту из Битрикса по его компании/контакту, брокеру и админу — по рейсам."""
    p = await access.get_participant(session, user_id)
    if p and p.status == "active" and p.role == "client":
        deals = await bitrix_client.list_client_deals(p.bitrix_company_id, p.bitrix_contact_id)
        return [(int(d["ID"]), d.get("TITLE"), d.get("STAGE_ID")) for d in deals]
    out, seen = [], set()
    for tr in await access.trips_for_user(session, user_id):
        if tr.bitrix_deal_id and tr.bitrix_deal_id not in seen:
            seen.add(tr.bitrix_deal_id)
            out.append((tr.bitrix_deal_id, tr.bitrix_deal_title, tr.bitrix_stage_id))
    return out


async def send_deal_list(message: Message, user_id: int, lang: str):
    try:
        async with get_session() as session:
            deals = await _deals_for(session, user_id)
    except Exception as e:
        logger.error(f"Deal list failed for {user_id}: {e}")
        await message.answer(t(lang, "deal_load_error"))
        return
    if not deals:
        await message.answer(t(lang, "no_deals"))
        return
    kb = []
    for deal_id, title, stage in deals:
        label = f"#{deal_id} · {i18n.stage_name(lang, stage)} · {title or ''}"
        kb.append([InlineKeyboardButton(text=label[:64], callback_data=f"d:{deal_id}")])
    await message.answer(t(lang, "deals_header", n=len(deals)),
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")


@router.message(F.text.in_(V("btn_my_deals")))
async def my_deals(message: Message, state: FSMContext, lang: str = "ru"):
    uid = message.from_user.id
    if not access.is_admin(uid):
        async with get_session() as session:
            p = await access.get_participant(session, uid)
        if not p or p.status != "active":
            raise SkipHandler()
    await state.clear()
    await send_deal_list(message, uid, lang)


async def can_view_deal(session, user_id: int, deal: dict) -> bool:
    if access.is_admin(user_id):
        return True
    p = await access.get_participant(session, user_id)
    if not p or p.status != "active":
        return False
    if p.role == "client":
        company = str(deal.get("COMPANY_ID") or "")
        contact = str(deal.get("CONTACT_ID") or "")
        return bool((p.bitrix_company_id and company == str(p.bitrix_company_id)) or
                    (p.bitrix_contact_id and contact == str(p.bitrix_contact_id)))
    if p.role == "broker":
        for tr in await crud.list_trips_by_deal(session, int(deal["ID"]), limit=20):
            if await access.can_view(session, user_id, tr):
                return True
    return False


def _bitrix_date(value) -> str:
    from src.services.trips import _parse_dt
    dt = _parse_dt(value)
    return msk(dt, "%d.%m.%Y") if dt else ""


def _driver_phone(value) -> Optional[str]:
    text = str(value or "").strip()
    return text if sum(ch.isdigit() for ch in text) >= 7 else None


async def deal_card(session, deal: dict, lang: str):
    from aiogram.types import CopyTextButton
    deal_id = int(deal["ID"])
    lines = [f"📋 <b>#{deal_id} {escape(deal.get('TITLE') or '')}</b>",
             t(lang, "deal_stage", stage=escape(i18n.stage_name(lang, deal.get("STAGE_ID"))))]
    terminal = deal.get(settings.bitrix_field_terminal)
    if terminal:
        lines.append(t(lang, "deal_terminal", terminal=escape(i18n.terminal_name(lang, terminal))))
        addr = i18n.terminal_address(lang, terminal)
        if addr:
            lines.append(f"     {escape(addr)}")
    truck = deal.get(settings.bitrix_field_truck_number) or deal.get(settings.bitrix_field_truck_number_alt)
    if truck:
        lines.append(t(lang, "deal_vehicle", truck=escape(str(truck))))
    for key, field in (("deal_shipped", settings.bitrix_field_shipment_date),
                       ("deal_planned", settings.bitrix_field_planned_arrival),
                       ("deal_arrived", settings.bitrix_field_actual_arrival)):
        d = _bitrix_date(deal.get(field))
        if d:
            lines.append(t(lang, key, d=d))

    # Водитель: из рейсов бота по этой сделке
    kb = []
    trips = await crud.list_trips_by_deal(session, deal_id)
    lines.append(t(lang, "deal_drivers"))
    shown = 0
    for tr in trips:
        driver = await crud.get_driver_by_id(session, tr.driver_id) if tr.driver_id else None
        if not driver:
            continue
        loc = await crud.get_last_trip_location(session, tr)
        name = escape(" ".join(x for x in [driver.first_name, driver.last_name] if x) or t(lang, "driver_word"))
        contact = f" (@{escape(driver.username)})" if driver.username else ""
        seen = i18n.ago(lang, loc.recorded_at) if loc else t(lang, "no_points_short")
        mark = "🟢 " if tr.status == "active" else "⚪ "
        lines.append(mark + t(lang, "deal_driver_line", name=name, contact=contact, truck=escape(tr.truck_number),
                              seen=seen))
        row = [InlineKeyboardButton(text=f"{t(lang, 'btn_open_trip')} {tr.truck_number}"[:40],
                                    callback_data=f"v:t:{tr.id}")]
        if driver.username and shown == 0:
            row.append(InlineKeyboardButton(text=t(lang, "btn_driver_chat")[:40], url=f"https://t.me/{driver.username}"))
        kb.append(row)
        shown += 1
    phone = _driver_phone(deal.get(settings.bitrix_field_driver_phone))
    if phone:
        lines.append(t(lang, "deal_driver_phone", phone=escape(phone)))
    if not shown and not phone:
        lines.append(t(lang, "deal_no_driver"))

    # Комментарии менеджера
    comments = deal.get(settings.bitrix_field_client_comments)
    if isinstance(comments, list):
        comments = "\n".join(str(x) for x in comments if x)
    comments = (comments or "").replace("\r", "").strip()
    if comments:
        lines.append(t(lang, "deal_comments", text=escape(comments[:1500])))

    # Тема письма
    subject = (deal.get(settings.bitrix_field_email_subject) or "").strip()
    if subject:
        lines.append(t(lang, "deal_subject", subject=escape(subject)))
        kb.insert(0, [InlineKeyboardButton(text=t(lang, "btn_copy_subject"),
                                           copy_text=CopyTextButton(text=subject[:256]))])

    kb.append([InlineKeyboardButton(text=t(lang, "btn_refresh"), callback_data=f"d:{deal_id}"),
               InlineKeyboardButton(text=t(lang, "btn_all_deals"), callback_data="d:list")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "d:list")
async def cb_deal_list(cb: CallbackQuery, lang: str = "ru"):
    await send_deal_list(cb.message, cb.from_user.id, lang)
    await cb.answer()


@router.callback_query(F.data.regexp(r"^d:\d+$"))
async def cb_deal(cb: CallbackQuery, lang: str = "ru"):
    deal_id = int(cb.data.split(":")[1])
    try:
        deal = await bitrix_client.get_deal(deal_id)
    except Exception as e:
        logger.error(f"Cannot load deal {deal_id}: {e}")
        deal = None
    if not deal or not deal.get("ID"):
        await cb.answer(t(lang, "deal_load_error"), show_alert=True)
        return
    async with get_session() as session:
        if not await can_view_deal(session, cb.from_user.id, deal):
            await cb.answer(t(lang, "no_access_deal"), show_alert=True)
            return
        text, kb = await deal_card(session, deal, lang)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await cb.answer()


# ==================== НОВЫЙ РЕЙС (брокер / админ) ====================

@router.message(F.text.in_(V("btn_create_trip")), CanCreateTrip())
async def new_trip_start(message: Message, state: FSMContext, lang: str = "ru"):
    await state.set_state(RoleStates.new_trip_truck)
    await message.answer(t(lang, "new_trip_truck_ask"), reply_markup=keyboards.cancel_keyboard(lang))


@router.message(RoleStates.new_trip_truck)
async def new_trip_truck(message: Message, state: FSMContext, lang: str = "ru"):
    if await _cancel(message, state, lang):
        return
    from src.bot.handlers import validate_plate_number
    truck = (message.text or "").strip().upper().replace(" ", "").replace("-", "")
    if not validate_plate_number(truck):
        await message.answer(t(lang, "bad_plate"))
        return
    await state.update_data(truck=truck)
    await state.set_state(RoleStates.new_trip_inn)
    await message.answer(t(lang, "new_trip_inn_ask", btn=t(lang, "btn_skip")), reply_markup=keyboards.skip_keyboard(lang))


@router.message(RoleStates.new_trip_inn)
async def new_trip_inn(message: Message, state: FSMContext, lang: str = "ru"):
    if await _cancel(message, state, lang):
        return
    text = (message.text or "").strip()
    inn = "".join(ch for ch in text if ch.isdigit())
    skip = text in V("btn_skip")
    if not skip and len(inn) not in (10, 12):
        await message.answer(t(lang, "inn_or_skip", btn=t(lang, "btn_skip")))
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
    if inn and not skip and not deal:
        try:
            company = await bitrix_client.find_company_by_inn(inn)
        except Exception as e:
            logger.error(f"Bitrix INN lookup failed: {e}")

    async with get_session() as session:
        p = await access.get_participant(session, u.id)
        trip = await crud.create_trip(session, driver_id=None, truck_number=truck,
                                      created_by_participant_id=p.id if p else None)
        if deal:
            apply_deal_to_trip(trip, deal)
            who = "брокер" if p and p.role == "broker" else "диспетчер"
            await announce_link(session, trip, None, f"{who} {u.full_name} создал рейс в боте, водитель подключится по ссылке")
        elif company:
            trip.bitrix_company_id = company["company_id"]
        inv = await access.create_invite(session, "driver", u.id, trip_id=trip.id, days=30)
        trip_id, deal_id, deal_title, terminal_code = trip.id, trip.bitrix_deal_id, trip.bitrix_deal_title, trip.terminal_code
    await state.clear()

    link = access.invite_link(await bot_username(message.bot), "drv", inv.code)
    role = "admin" if access.is_admin(u.id) else "broker"
    lines = [t(lang, "trip_created", truck=escape(truck))]
    if deal_id:
        lines.append(t(lang, "tc_deal_found", title=escape(deal_title or ""),
                       terminal=escape(i18n.terminal_name(lang, terminal_code))))
    else:
        lines.append(t(lang, "tc_deal_not_found"))
    lines.append(t(lang, "tc_driver_link", link=link))
    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True,
                         reply_markup=menu_for(role, lang))
    if role == "broker":
        await notify_admins(
            "reg", f"➕ <b>Брокер {escape(u.full_name)} создал рейс</b> {escape(truck)}"
                   + (f"\n📋 сделка #{deal_id}" if deal_id else "\n⚠️ сделка не найдена"),
            InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🚛 Открыть рейс", callback_data=f"adm:trip:{trip_id}")]]),
        )


# ==================== НАПИСАТЬ ДИСПЕТЧЕРУ ====================

@router.message(F.text.in_(V("btn_write_dispatcher")), ActiveParticipant("client", "broker"))
async def write_dispatcher(message: Message, state: FSMContext, lang: str = "ru"):
    await state.set_state(RoleStates.write_dispatcher)
    await message.answer(t(lang, "write_dispatcher_ask"), reply_markup=keyboards.cancel_keyboard(lang))


@router.message(RoleStates.write_dispatcher)
async def write_dispatcher_text(message: Message, state: FSMContext, lang: str = "ru"):
    if await _cancel(message, state, lang):
        return
    if not message.text:
        await message.answer(t(lang, "only_text"))
        return
    await _forward_participant_text(message, state, lang)


@router.message(F.text & ~F.text.startswith("/"), ActiveParticipant("client", "broker"))
async def participant_free_text(message: Message, state: FSMContext, lang: str = "ru"):
    await _forward_participant_text(message, state, lang)


async def _forward_participant_text(message: Message, state: FSMContext, lang: str):
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
    await message.answer(t(lang, "sent_to_dispatcher"), reply_markup=menu_for(p.role, lang))
