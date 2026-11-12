"""
Сквозной тест бота на SQLite и поддельном Telegram/Битриксе:
регистрация водителя, геопозиция, админка, ручная привязка, сообщения,
блокировка, вебхук Битрикса, молчащие водители.

Запуск: python -m pytest -q tests
"""

import os
import tempfile
from datetime import datetime, timedelta
from itertools import count

_db = tempfile.mktemp(suffix=".db")
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{_db}",
    "TELEGRAM_BOT_TOKEN": "123456:TESTTOKEN",
    "BITRIX24_WEBHOOK_URL": "https://b24-za9auf.bitrix24.ru/rest/1/xxx/",
    "ADMIN_IDS": "1000",
    "APP_ENV": "test",
    "TELEGRAM_WEBHOOK_URL": "https://bot.test",
})

import pytest  # noqa: E402
import httpx  # noqa: E402
from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.methods import (  # noqa: E402
    AnswerCallbackQuery, EditMessageText, GetMe, SendLocation, SendMessage, SendVenue,
)
from aiogram.types import Chat, Message, Update, User  # noqa: E402

ADMIN = 1000
DRIVER1 = 2001
DRIVER2 = 2002
DRIVER3 = 2003
DRIVER4 = 2004
CLIENT = 3001
CLIENT2 = 3002
BROKER = 4001
BROKER2 = 4002
MANAGER = 5001

_ids = count(1)


class FakeSession(BaseSession):
    """Перехватывает все вызовы Telegram API."""

    def __init__(self):
        super().__init__()
        self.calls = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, GetMe):
            return User(id=1, is_bot=True, first_name="Bot", username="fleet_test_bot")
        if isinstance(method, (SendMessage, EditMessageText, SendLocation, SendVenue)):
            chat_id = getattr(method, "chat_id", None) or ADMIN
            return Message(message_id=next(_ids), date=datetime.now(),
                           chat=Chat(id=chat_id, type="private"),
                           text=getattr(method, "text", None))
        return True

    async def stream_content(self, *a, **kw):  # pragma: no cover
        yield b""

    async def close(self):
        pass

    def sent_to(self, chat_id):
        out = []
        for m in self.calls:
            if isinstance(m, (SendMessage, EditMessageText)) and m.chat_id == chat_id:
                out.append(m.text)
        return out

    def kb_texts(self, chat_id):
        """Тексты и callback_data кнопок в сообщениях этому чату"""
        out = []
        for m in self.calls:
            if isinstance(m, (SendMessage, EditMessageText)) and m.chat_id == chat_id and m.reply_markup is not None:
                rows = getattr(m.reply_markup, "inline_keyboard", None) or []
                for row in rows:
                    for b in row:
                        out.append(f"{b.text}|{b.callback_data or b.url}")
        return out

    def alerts(self):
        return [m.text for m in self.calls if isinstance(m, AnswerCallbackQuery) and m.text]

    def clear(self):
        self.calls.clear()


DEAL_100 = {
    "ID": "100", "TITLE": "Курага ООО Ромашка", "STAGE_ID": "UC_SDO64X", "CLOSED": "N",
    "COMPANY_ID": "50", "CONTACT_ID": "25726",
    "UF_CRM_1586456781744": "01A123BC", "UF_CRM_1711445194523": "86",
    "UF_CRM_1713519647288": "2026-11-05T03:00:00+03:00",
}
DEAL_555 = {
    "ID": "555", "TITLE": "Изюм ИП Иванов", "STAGE_ID": "UC_SDO64X", "CLOSED": "N",
    "UF_CRM_1586456781744": "777XYZ", "UF_CRM_1711445194523": "302",
}


@pytest.fixture(scope="module")
def env():
    return {}


@pytest.fixture(scope="module")
async def app(env):
    from src.db.database import init_db
    from src.bot import router as bot_router
    from src.bot.admin import router as admin_router
    from src.bot.roles import router as roles_router
    from src.services import notify
    from src.services.bitrix import bitrix_client
    from src.services.geocoder import maps_service
    from src.api import set_bot_and_dispatcher

    await init_db()
    session = FakeSession()
    bot = Bot(token="123456:TESTTOKEN", session=session)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(roles_router)
    dp.include_router(bot_router)
    notify.set_notify_bot(bot)
    set_bot_and_dispatcher(bot, dp)

    bx = {"comments": [], "updates": [], "stages": []}
    geo = {"country": "kz", "address": "Казахстан, трасса М-32"}
    deals = {"100": DEAL_100, "555": DEAL_555}

    async def find_deal(truck):
        return DEAL_100 if truck == "01A123BC" else None

    async def get_deal(deal_id):
        return deals.get(str(deal_id))

    async def add_comment(deal_id, text):
        bx["comments"].append((deal_id, text))
        return True

    async def update_tg(deal_id, tg, username=None):
        bx["updates"].append((deal_id, tg))
        return True

    async def add_loc(deal_id, address, lat, lon, distance_km=None, eta=None):
        bx["comments"].append((deal_id, f"loc {address}"))
        return True

    async def reverse(lat, lon):
        return geo["address"], geo["country"]

    async def find_client(phone):
        if "".join(c for c in phone if c.isdigit()).endswith("9263602326"):
            return {"contact_id": 25726, "company_id": 50, "contact_name": "Мария",
                    "company_title": "СОГДИАНА"}
        return None

    async def find_inn(inn):
        return {"company_id": 50, "company_title": "СОГДИАНА"} if inn == "7726605312" else None

    async def set_stage(deal_id, stage):
        bx["stages"].append((deal_id, stage))
        return True

    async def update_deal(deal_id, fields):
        return True

    async def dist(lat, lon, code):
        return {"distance_km": 150.0, "eta_text": "2 ч."} if code == "86" else None

    bitrix_client.find_deal_by_truck_number = find_deal
    bitrix_client.get_deal = get_deal
    bitrix_client.add_timeline_comment = add_comment
    bitrix_client.update_driver_telegram_id = update_tg
    bitrix_client.add_location_comment = add_loc
    maps_service.reverse_details = reverse
    bitrix_client.find_client_by_phone = find_client
    bitrix_client.find_company_by_inn = find_inn
    bitrix_client.set_stage = set_stage
    bitrix_client.update_deal = update_deal
    maps_service.get_distance_to_terminal = dist

    env.update(bot=bot, dp=dp, s=session, bx=bx, deals=deals, geo=geo)
    return env


_upd = count(1)


def _user(uid):
    return {"id": uid, "is_bot": False, "first_name": f"User{uid}", "username": f"u{uid}"}


async def text(env, uid, txt):
    upd = Update.model_validate({"update_id": next(_upd), "message": {
        "message_id": next(_ids), "date": int(datetime.now().timestamp()),
        "chat": {"id": uid, "type": "private"}, "from": _user(uid), "text": txt,
        **({"entities": [{"type": "bot_command", "offset": 0, "length": len(txt.split()[0])}]}
           if txt.startswith("/") else {}),
    }})
    await env["dp"].feed_update(env["bot"], upd)


async def location(env, uid, lat=50.0, lon=60.0):
    upd = Update.model_validate({"update_id": next(_upd), "message": {
        "message_id": next(_ids), "date": int(datetime.now().timestamp()),
        "chat": {"id": uid, "type": "private"}, "from": _user(uid),
        "location": {"latitude": lat, "longitude": lon},
    }})
    await env["dp"].feed_update(env["bot"], upd)


async def contact(env, uid, phone):
    upd = Update.model_validate({"update_id": next(_upd), "message": {
        "message_id": next(_ids), "date": int(datetime.now().timestamp()),
        "chat": {"id": uid, "type": "private"}, "from": _user(uid),
        "contact": {"phone_number": phone, "first_name": "X", "user_id": uid},
    }})
    await env["dp"].feed_update(env["bot"], upd)


async def press(env, uid, data):
    upd = Update.model_validate({"update_id": next(_upd), "callback_query": {
        "id": str(next(_ids)), "from": _user(uid), "chat_instance": "x", "data": data,
        "message": {"message_id": 1, "date": int(datetime.now().timestamp()),
                    "chat": {"id": uid, "type": "private"}, "text": "old"},
    }})
    await env["dp"].feed_update(env["bot"], upd)


async def settle():
    import asyncio
    for _ in range(5):
        await asyncio.sleep(0.02)


def joined(lst):
    return "\n".join(x or "" for x in lst)


# ==================== ТЕСТЫ ====================

async def test_driver_registers_with_deal(app):
    s = app["s"]
    await text(app, DRIVER1, "/start")
    assert "Кто вы?" in joined(s.sent_to(DRIVER1))
    await text(app, DRIVER1, "🚛 Я водитель")
    assert "отправитель груза и получатель груза" in joined(s.sent_to(DRIVER1))
    await text(app, DRIVER1, "✅ Даю согласие на передачу геолокации")
    s.clear()
    await text(app, DRIVER1, "01a123bc")
    await settle()
    out = joined(s.sent_to(DRIVER1))
    assert "Регистрация завершена" in out
    assert "Коломна" in out and "Северная звезда" in out
    assert "86\n" not in out
    admin = joined(s.sent_to(ADMIN))
    assert "Водитель зарегистрировался" in admin and "#100" in admin
    assert "granica2004.bitrix24.ru/crm/deal/details/100/" in admin
    assert ("100" in [str(d) for d, _ in app["bx"]["updates"]]) or (100 in [d for d, _ in app["bx"]["updates"]])


async def test_location_synced(app):
    s = app["s"]
    s.clear()
    await location(app, DRIVER1)
    out = joined(s.sent_to(DRIVER1))
    assert "Локация сохранена" in out and "150 км" in out and "отправлены брокеру" in out


async def test_terminal_address_button(app):
    s = app["s"]
    s.clear()
    await text(app, DRIVER1, "📍 Терминал прибытия")
    out = joined(s.sent_to(DRIVER1))
    assert "Автомобилистов" in out and "Терминал прибытия" in out
    assert any("rtext=~55.116124,38.730962" in k for k in s.kb_texts(DRIVER1))
    assert any(isinstance(m, SendVenue) for m in s.calls)
    s.clear()
    await text(app, DRIVER1, "🏭 Адрес терминала назначения")  # старая кнопка у водителей
    assert "Автомобилистов" in joined(s.sent_to(DRIVER1))


async def test_admin_menu_and_card(app):
    s = app["s"]
    s.clear()
    await text(app, ADMIN, "/admin")
    out = joined(s.sent_to(ADMIN))
    assert "В пути: <b>1</b>" in out and "Ближе 200 км" in out
    s.clear()
    await press(app, ADMIN, "adm:trips:a:0")
    await press(app, ADMIN, "adm:trips:n:0")
    from src.db.database import get_session
    from src.db import crud
    async with get_session() as session:
        trip = (await crud.list_active_trips(session))[0]
    await press(app, ADMIN, f"adm:trip:{trip.id}")
    card = s.sent_to(ADMIN)[-1]
    assert "01A123BC" in card and "Коломна" in card and "150 км" in card and "Отгрузка: 05.11.2026" in card


async def test_non_admin_has_no_access(app):
    s = app["s"]
    s.clear()
    await text(app, DRIVER1, "/admin")
    assert "Админка" not in joined(s.sent_to(DRIVER1))
    await press(app, DRIVER1, "adm:menu")
    assert "Нет доступа" in s.alerts()


async def test_unlinked_driver_manual_bind(app):
    s = app["s"]
    await text(app, DRIVER2, "/start")
    await text(app, DRIVER2, "🚛 Я водитель")
    await text(app, DRIVER2, "✅ Даю согласие на передачу геолокации")
    s.clear()
    await text(app, DRIVER2, "777XYZ")
    await settle()
    assert "сделка не найдена" in joined(s.sent_to(ADMIN))
    from src.db.database import get_session
    from src.db import crud
    async with get_session() as session:
        d2 = await crud.get_driver_by_telegram_id(session, DRIVER2)
        trip = await crud.get_active_trip_by_driver(session, d2.id)
    s.clear()
    await press(app, ADMIN, "adm:trips:u:0")
    assert "777XYZ" in str(s.calls[0])  # кнопка рейса в списке без сделки
    await press(app, ADMIN, f"adm:bind:{trip.id}")
    await text(app, ADMIN, "абв")
    assert "Нужно число" in joined(s.sent_to(ADMIN))
    await text(app, ADMIN, "555")
    assert "Рейс привязан к сделке" in joined(s.sent_to(ADMIN))
    assert "Новосибирск" in joined(s.sent_to(DRIVER2))
    async with get_session() as session:
        trip = await crud.get_trip_by_id(session, trip.id)
        assert trip.bitrix_deal_id == 555 and trip.terminal_code == "302"


async def test_driver_message_and_admin_reply(app):
    s = app["s"]
    s.clear()
    await text(app, DRIVER1, "Стою на границе, очередь")
    assert "Сообщение от водителя" in joined(s.sent_to(ADMIN))
    assert "передано диспетчеру" in joined(s.sent_to(DRIVER1))
    from src.db.database import get_session
    from src.db import crud
    async with get_session() as session:
        d1 = await crud.get_driver_by_telegram_id(session, DRIVER1)
    s.clear()
    await press(app, ADMIN, f"adm:msg:{d1.id}")
    await text(app, ADMIN, "Понял, держите в курсе")
    assert "Сообщение от диспетчера" in joined(s.sent_to(DRIVER1))


async def test_ask_location(app):
    s = app["s"]
    from src.db.database import get_session
    from src.db import crud
    async with get_session() as session:
        d1 = await crud.get_driver_by_telegram_id(session, DRIVER1)
        trip = await crud.get_active_trip_by_driver(session, d1.id)
    s.clear()
    await press(app, ADMIN, f"adm:ask:{trip.id}")
    assert "Диспетчер просит" in joined(s.sent_to(DRIVER1))


async def test_silent_alert_once(app):
    s = app["s"]
    from src.db.database import get_session
    from src.db import crud
    from src.db.models import Location
    from sqlalchemy import update
    from src.services.scheduler import check_silent_drivers
    async with get_session() as session:
        await session.execute(update(Location).values(recorded_at=datetime.utcnow() - timedelta(hours=30)))
    s.clear()
    await check_silent_drivers()
    first = joined(s.sent_to(ADMIN))
    assert "Водитель молчит" in first and "01A123BC" in first
    s.clear()
    await check_silent_drivers()
    assert "01A123BC" not in joined(s.sent_to(ADMIN))  # повторно не шлём
    # водитель прислал точку — тревога сбрасывается
    await location(app, DRIVER1)
    s.clear()
    await check_silent_drivers()
    assert "01A123BC" not in joined(s.sent_to(ADMIN))


async def test_notify_toggle(app):
    s = app["s"]
    await press(app, ADMIN, "adm:ntf:reg")
    from src.services.notify import event_enabled
    assert await event_enabled("reg") is False
    await press(app, ADMIN, "adm:ntf:reg")
    assert await event_enabled("reg") is True


async def test_terminals_screen(app):
    s = app["s"]
    s.clear()
    await press(app, ADMIN, "adm:term")
    out = joined(s.sent_to(ADMIN))
    assert "Владивосток" in out and "Троицк" in out and "✅ <code>86</code>" in out


# ==================== РОЛИ ====================

import re  # noqa: E402


async def _trip100():
    from src.db.database import get_session
    from src.db import crud
    async with get_session() as session:
        return await crud.get_active_trip_by_deal(session, 100)


async def _pid(tg):
    from src.db.database import get_session
    from src.services import access
    async with get_session() as session:
        return (await access.get_participant(session, tg)).id


def _link(texts, prefix):
    m = re.search(prefix + r"_([A-Za-z0-9]+)", joined(texts))
    assert m, joined(texts)
    return m.group(1)


async def test_client_by_phone_sees_trip(app):
    s = app["s"]
    s.clear()
    await text(app, CLIENT, "/start")
    await text(app, CLIENT, "📦 Я получатель груза")
    await contact(app, CLIENT, "+7 926 360-23-26")
    out = joined(s.sent_to(CLIENT))
    assert "Нашли вас" in out and "СОГДИАНА" in out
    trip = await _trip100()
    assert any(f"v:t:{trip.id}" in k for k in s.kb_texts(CLIENT))
    assert "Новый клиент" in joined(s.sent_to(ADMIN))
    s.clear()
    await press(app, CLIENT, f"v:t:{trip.id}")
    card = joined(s.sent_to(CLIENT))
    assert "01A123BC" in card and "Сейчас:" in card and "Коломна" in card
    assert any("https://bot.test/track/" in k for k in s.kb_texts(CLIENT))
    s.clear()
    await press(app, CLIENT, f"v:h:{trip.id}")
    assert "История 01A123BC" in joined(s.sent_to(CLIENT))
    await press(app, CLIENT, f"v:loc:{trip.id}")
    assert any(isinstance(m, SendLocation) and m.chat_id == CLIENT for m in s.calls)


async def test_track_page(app):
    from src.main import app as fastapi_app
    from src.services import access
    trip = await _trip100()
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get(f"/track/{trip.id}/{access.track_sig(trip.id)}")
        bad = await c.get(f"/track/{trip.id}/wrongsig")
    assert r.status_code == 200 and "01A123BC" in r.text and "leaflet" in r.text and '"lat": 50.0' in r.text
    assert bad.status_code == 404


async def test_border_and_arrival_events(app):
    s = app["s"]
    trip = await _trip100()
    s.clear()
    app["geo"].update(country="ru", address="Россия, Оренбургская область")
    await location(app, DRIVER1, 51.5, 55.1)
    assert "въехала в Россию" in joined(s.sent_to(CLIENT))
    assert "въехала в Россию" in joined(s.sent_to(ADMIN))
    s.clear()
    app["geo"].update(address="Коломна, проезд Автомобилистов")
    await location(app, DRIVER1, 55.1165, 38.7310)
    assert "Машина у терминала" in joined(s.sent_to(CLIENT))
    assert any(f"adm:arr:{trip.id}" in k for k in s.kb_texts(ADMIN))
    s.clear()
    await location(app, DRIVER1, 55.1166, 38.7311)
    assert "Машина у терминала" not in joined(s.sent_to(CLIENT))  # один раз
    await press(app, ADMIN, f"adm:arr:{trip.id}")
    assert (100, "9") in app["bx"]["stages"]


async def test_client_by_inn_needs_approval(app):
    s = app["s"]
    await text(app, CLIENT2, "/start")
    await text(app, CLIENT2, "📦 Я получатель груза")
    await contact(app, CLIENT2, "+70000000000")
    assert "ИНН" in joined(s.sent_to(CLIENT2))
    s.clear()
    await text(app, CLIENT2, "7726605312")
    assert "Заявка отправлена" in joined(s.sent_to(CLIENT2))
    assert "Клиент просит доступ" in joined(s.sent_to(ADMIN))
    s.clear()
    await text(app, CLIENT2, "📦 Мои рейсы")  # пока заявка не одобрена — рейсов не видно
    assert "01A123BC" not in str(s.calls)
    pid = await _pid(CLIENT2)
    await press(app, ADMIN, f"adm:pp:ok:{pid}")
    assert "Доступ открыт" in joined(s.sent_to(CLIENT2))
    s.clear()
    await text(app, CLIENT2, "📦 Мои рейсы")
    assert any("01A123BC" in k for k in s.kb_texts(CLIENT2))


async def test_broker_invite_creates_trip_and_driver_link(app):
    s = app["s"]
    s.clear()
    await press(app, ADMIN, "adm:inv:broker")
    code = _link(s.sent_to(ADMIN), "inv")
    s.clear()
    await text(app, BROKER, f"/start inv_{code}")
    assert "отправитель / брокер" in joined(s.sent_to(BROKER))
    await text(app, BROKER2, f"/start inv_{code}")  # одноразовая
    assert "недействительна" in joined(s.sent_to(BROKER2))
    s.clear()
    await text(app, BROKER, "➕ Новый рейс")
    await text(app, BROKER, "05B555CC")
    await text(app, BROKER, "Пропустить")
    dcode = _link(s.sent_to(BROKER), "drv")
    assert "Брокер" in joined(s.sent_to(ADMIN)) and "05B555CC" in joined(s.sent_to(ADMIN))
    s.clear()
    await text(app, DRIVER3, f"/start drv_{dcode}")
    assert "отправитель груза и получатель груза" in joined(s.sent_to(DRIVER3))
    await text(app, DRIVER3, "✅ Даю согласие на передачу геолокации")
    assert "Вы подключены к рейсу" in joined(s.sent_to(DRIVER3))
    assert "Груз в пути" in joined(s.sent_to(BROKER))
    await location(app, DRIVER3)
    s.clear()
    await text(app, BROKER, "📦 Мои рейсы")
    keys = s.kb_texts(BROKER)
    assert any("05B555CC" in k for k in keys) and not any("01A123BC" in k for k in keys)
    trip = await _trip100()
    await press(app, BROKER, f"v:t:{trip.id}")
    assert "Нет доступа к этому рейсу" in s.alerts()
    s.clear()
    await press(app, ADMIN, f"adm:acct:{trip.id}:{await _pid(BROKER)}")
    assert "Вам открыт рейс 01A123BC" in joined(s.sent_to(BROKER))
    s.clear()
    await press(app, BROKER, f"v:t:{trip.id}")
    assert "01A123BC" in joined(s.sent_to(BROKER))


async def test_admin_trip_driver_joins_by_number(app):
    s = app["s"]
    s.clear()
    await text(app, ADMIN, "➕ Новый рейс")
    await text(app, ADMIN, "07C777DD")
    await text(app, ADMIN, "Пропустить")
    assert "start=drv_" in joined(s.sent_to(ADMIN))
    await text(app, DRIVER4, "/start")
    await text(app, DRIVER4, "🚛 Я водитель")
    await text(app, DRIVER4, "✅ Даю согласие на передачу геолокации")
    s.clear()
    await text(app, DRIVER4, "07c777dd")
    assert "Вы подключены к рейсу" in joined(s.sent_to(DRIVER4))
    assert "Водитель подключился к рейсу" in joined(s.sent_to(ADMIN))


async def test_broker_self_registration(app):
    s = app["s"]
    await text(app, BROKER2, "/start")
    await text(app, BROKER2, "🌍 Я отправитель / брокер")
    await contact(app, BROKER2, "+992900000000")
    s.clear()
    await text(app, BROKER2, "Sugd Logistics, Таджикистан")
    assert "Брокер / отправитель просит доступ" in joined(s.sent_to(ADMIN))
    s.clear()
    await text(app, BROKER2, "➕ Новый рейс")  # ещё не одобрен
    assert "Рейс" not in joined(s.sent_to(BROKER2)) or "создан" not in joined(s.sent_to(BROKER2))
    await press(app, ADMIN, f"adm:pp:ok:{await _pid(BROKER2)}")
    assert "Доступ открыт" in joined(s.sent_to(BROKER2))


async def test_managers(app):
    s = app["s"]
    s.clear()
    await press(app, ADMIN, "adm:inv:admin")
    code = _link(s.sent_to(ADMIN), "inv")
    await text(app, MANAGER, f"/start inv_{code}")
    s.clear()
    await text(app, MANAGER, "/admin")
    assert "Админка" in joined(s.sent_to(MANAGER))
    await press(app, MANAGER, "adm:inv:admin")
    assert "Только владелец" in s.alerts()
    # владелец делает брокера админом и обратно
    bpid = await _pid(BROKER2)
    await press(app, ADMIN, f"adm:mkadm:{bpid}")
    s.clear()
    await text(app, BROKER2, "/admin")
    assert "Админка" in joined(s.sent_to(BROKER2))
    await press(app, ADMIN, f"adm:mkadm:{bpid}")
    s.clear()
    await text(app, BROKER2, "/admin")
    assert "Админка" not in joined(s.sent_to(BROKER2))
    # менеджер получает уведомления
    s.clear()
    await text(app, CLIENT, "Когда приедет машина?")
    assert "Сообщение" in joined(s.sent_to(MANAGER)) and "Сообщение" in joined(s.sent_to(ADMIN))
    await press(app, ADMIN, f"adm:pm:{await _pid(CLIENT)}")
    await text(app, ADMIN, "Завтра утром")
    assert "Сообщение от диспетчера" in joined(s.sent_to(CLIENT))


async def test_people_screens(app):
    s = app["s"]
    s.clear()
    await press(app, ADMIN, "adm:ppl")
    await press(app, ADMIN, "adm:pl:c:0")
    await press(app, ADMIN, f"adm:p:{await _pid(CLIENT)}")
    out = joined(s.sent_to(ADMIN))
    assert "Клиенты" in out and "Компания #50" in out
    trip = await _trip100()
    s.clear()
    await press(app, ADMIN, f"adm:acc:{trip.id}")
    out = joined(s.sent_to(ADMIN))
    assert "Кто видит рейс" in out and "СОГДИАНА" in out


async def test_bitrix_webhook_finishes_trip(app):
    s = app["s"]
    from src.main import app as fastapi_app
    app["deals"]["100"] = {**DEAL_100, "STAGE_ID": "9"}
    s.clear()
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/webhook/bitrix24/deal-update",
                         data={"event": "ONCRMDEALUPDATE", "data[FIELDS][ID]": "100",
                               "auth[application_token]": "tok"})
    assert r.status_code == 200 and r.json()["message"] == "Trip completed"
    assert "Перевозка завершена" in joined(s.sent_to(DRIVER1))
    assert "Рейс завершён по стадии" in joined(s.sent_to(ADMIN))


async def test_bitrix_webhook_matches_waiting(app):
    """Водитель ждёт сделку → в Битриксе вписали номер → автопривязка."""
    s = app["s"]
    from src.main import app as fastapi_app
    await text(app, DRIVER1, "🔄 Новая перевозка")
    await text(app, DRIVER1, "99ZZZ")  # сделки пока нет
    app["deals"]["700"] = {"ID": "700", "TITLE": "Орехи", "STAGE_ID": "NEW", "CLOSED": "N",
                           "UF_CRM_1586456781744": "99zzz", "UF_CRM_1711445194523": "300"}
    s.clear()
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/webhook/bitrix24/deal-update", data={"data[FIELDS][ID]": "700"})
    assert r.json()["message"] == "Registration matched"
    assert "Сделка найдена" in joined(s.sent_to(DRIVER1)) and "Екатеринбург" in joined(s.sent_to(DRIVER1))
    assert "Рейс привязан к сделке" in joined(s.sent_to(ADMIN))


async def test_block_driver(app):
    s = app["s"]
    from src.db.database import get_session
    from src.db import crud
    async with get_session() as session:
        d2 = await crud.get_driver_by_telegram_id(session, DRIVER2)
    await press(app, ADMIN, f"adm:blk:{d2.id}")
    s.clear()
    await text(app, DRIVER2, "/start")
    assert "Доступ к боту закрыт" in joined(s.sent_to(DRIVER2))
    await location(app, DRIVER2)
    assert "Локация сохранена" not in joined(s.sent_to(DRIVER2))
    await press(app, ADMIN, f"adm:blk:{d2.id}")


async def test_finish_from_admin(app):
    s = app["s"]
    from src.db.database import get_session
    from src.db import crud
    async with get_session() as session:
        d2 = await crud.get_driver_by_telegram_id(session, DRIVER2)
        trip = await crud.get_active_trip_by_driver(session, d2.id)
    s.clear()
    await press(app, ADMIN, f"adm:finok:{trip.id}")
    assert "завершена диспетчером" in joined(s.sent_to(DRIVER2))
    async with get_session() as session:
        assert (await crud.get_trip_by_id(session, trip.id)).status == "completed"
