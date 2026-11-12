"""
Роли и доступ к рейсам.

Роли:
  owner   — владелец, Telegram ID из ADMIN_IDS (нельзя удалить из бота)
  admin   — менеджер; видит и делает всё, кроме управления админами
  broker  — брокер/отправитель; видит созданные им рейсы и открытые ему админом
  client  — получатель; видит рейсы по сделкам своей компании (или своего контакта)
  driver  — водитель; видит свой рейс

Доступ клиента определяется по сделке: COMPANY_ID / CONTACT_ID сделки == компания / контакт клиента.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Set

from loguru import logger
from sqlalchemy import and_, delete, or_, select

from src.config import get_settings
from src.db.models import Driver, Invite, Participant, Trip, TripAccess

settings = get_settings()

ROLE_TITLES = {
    "owner": "владелец",
    "admin": "менеджер (админ)",
    "broker": "брокер / отправитель",
    "client": "клиент / получатель",
    "driver": "водитель",
}

# Менеджеры-админы из БД (кэш; обновляется при изменениях)
_db_admins: Set[int] = set()


def is_owner(user_id: int) -> bool:
    return user_id in settings.admin_ids


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids or user_id in _db_admins


def all_admin_ids() -> List[int]:
    return list(dict.fromkeys(list(settings.admin_ids) + sorted(_db_admins)))


async def reload_admins(session) -> None:
    result = await session.execute(
        select(Participant.telegram_id).where(
            and_(Participant.role == "admin", Participant.status == "active")
        )
    )
    _db_admins.clear()
    _db_admins.update(int(x) for x in result.scalars().all())
    logger.info(f"Admins reloaded: owners={settings.admin_ids}, managers={sorted(_db_admins)}")


# ==================== УЧАСТНИКИ ====================

async def get_participant(session, telegram_id: int) -> Optional[Participant]:
    result = await session.execute(select(Participant).where(Participant.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_participant_by_id(session, pid: int) -> Optional[Participant]:
    result = await session.execute(select(Participant).where(Participant.id == pid))
    return result.scalar_one_or_none()


async def upsert_participant(session, telegram_id: int, **fields) -> Participant:
    p = await get_participant(session, telegram_id)
    if not p:
        p = Participant(telegram_id=telegram_id, **fields)
        session.add(p)
    else:
        for k, v in fields.items():
            setattr(p, k, v)
        p.updated_at = datetime.utcnow()
    await session.flush()
    return p


async def list_participants(session, role: Optional[str] = None, status: Optional[str] = None) -> List[Participant]:
    q = select(Participant)
    if role:
        q = q.where(Participant.role == role)
    if status:
        q = q.where(Participant.status == status)
    result = await session.execute(q.order_by(Participant.created_at.desc()))
    return list(result.scalars().all())


async def role_of(session, telegram_id: int) -> Optional[str]:
    """Роль пользователя: owner/admin/broker/client/driver/None (pending и blocked — None)."""
    if is_owner(telegram_id):
        return "owner"
    p = await get_participant(session, telegram_id)
    if p and p.status == "active":
        return p.role
    result = await session.execute(select(Driver).where(Driver.telegram_id == telegram_id))
    d = result.scalar_one_or_none()
    if d and d.consent_given and d.is_active:
        return "driver"
    return None


# ==================== ДОСТУП К РЕЙСАМ ====================

def _client_filter(p: Participant):
    conds = []
    if p.bitrix_company_id:
        conds.append(Trip.bitrix_company_id == p.bitrix_company_id)
    if p.bitrix_contact_id:
        conds.append(Trip.bitrix_contact_id == p.bitrix_contact_id)
    return or_(*conds) if conds else None


async def trips_for_user(session, telegram_id: int, recent_days: int = 30) -> List[Trip]:
    """Рейсы, которые пользователь может смотреть: активные + завершённые за recent_days."""
    since = datetime.utcnow() - timedelta(days=recent_days)
    fresh = or_(Trip.status == "active", Trip.completed_at >= since)

    if is_admin(telegram_id):
        q = select(Trip).where(fresh)
    else:
        p = await get_participant(session, telegram_id)
        if not p or p.status != "active":
            return []
        if p.role == "client":
            cond = _client_filter(p)
            if cond is None:
                return []
            q = select(Trip).where(and_(fresh, cond))
        elif p.role == "broker":
            shared = select(TripAccess.trip_id).where(TripAccess.participant_id == p.id)
            q = select(Trip).where(and_(fresh, or_(
                Trip.created_by_participant_id == p.id, Trip.id.in_(shared),
            )))
        else:
            return []
    result = await session.execute(q.order_by(Trip.status.asc(), Trip.started_at.desc()).limit(30))
    return list(result.scalars().all())


async def can_view(session, telegram_id: int, trip: Trip) -> bool:
    if not trip:
        return False
    if is_admin(telegram_id):
        return True
    if trip.driver_id:
        result = await session.execute(select(Driver).where(Driver.id == trip.driver_id))
        d = result.scalar_one_or_none()
        if d and d.telegram_id == telegram_id:
            return True
    p = await get_participant(session, telegram_id)
    if not p or p.status != "active":
        return False
    if p.role == "client":
        return bool((p.bitrix_company_id and trip.bitrix_company_id == p.bitrix_company_id) or
                    (p.bitrix_contact_id and trip.bitrix_contact_id == p.bitrix_contact_id))
    if p.role == "broker":
        if trip.created_by_participant_id == p.id:
            return True
        result = await session.execute(select(TripAccess.id).where(
            and_(TripAccess.trip_id == trip.id, TripAccess.participant_id == p.id)))
        return result.first() is not None
    return False


async def watchers(session, trip: Trip) -> List[Participant]:
    """Клиенты и брокеры, которым показывается рейс (для рассылки событий)."""
    conds = []
    if trip.bitrix_company_id:
        conds.append(and_(Participant.role == "client", Participant.bitrix_company_id == trip.bitrix_company_id))
    if trip.bitrix_contact_id:
        conds.append(and_(Participant.role == "client", Participant.bitrix_contact_id == trip.bitrix_contact_id))
    if trip.created_by_participant_id:
        conds.append(Participant.id == trip.created_by_participant_id)
    shared = select(TripAccess.participant_id).where(TripAccess.trip_id == trip.id)
    conds.append(and_(Participant.role == "broker", Participant.id.in_(shared)))
    result = await session.execute(
        select(Participant).where(and_(Participant.status == "active", or_(*conds)))
    )
    seen, out = set(), []
    for p in result.scalars().all():
        if p.telegram_id not in seen and not is_admin(p.telegram_id):
            seen.add(p.telegram_id)
            out.append(p)
    return out


async def brokers_with_access(session, trip_id: int) -> List[Participant]:
    shared = select(TripAccess.participant_id).where(TripAccess.trip_id == trip_id)
    result = await session.execute(select(Participant).where(Participant.id.in_(shared)))
    return list(result.scalars().all())


async def toggle_broker_access(session, trip_id: int, participant_id: int) -> bool:
    """Открыть/закрыть рейс брокеру. Возвращает True, если теперь открыт."""
    result = await session.execute(select(TripAccess).where(
        and_(TripAccess.trip_id == trip_id, TripAccess.participant_id == participant_id)))
    row = result.scalar_one_or_none()
    if row:
        await session.execute(delete(TripAccess).where(TripAccess.id == row.id))
        return False
    session.add(TripAccess(trip_id=trip_id, participant_id=participant_id))
    await session.flush()
    return True


# ==================== ПРИГЛАШЕНИЯ ====================

async def create_invite(session, kind: str, created_by: int, trip_id: Optional[int] = None,
                        days: int = 7) -> Invite:
    inv = Invite(
        code=secrets.token_urlsafe(9).replace("-", "x").replace("_", "y"),
        kind=kind, trip_id=trip_id, created_by=created_by,
        expires_at=datetime.utcnow() + timedelta(days=days),
    )
    session.add(inv)
    await session.flush()
    return inv


async def get_invite(session, code: str) -> Optional[Invite]:
    result = await session.execute(select(Invite).where(Invite.code == code))
    inv = result.scalar_one_or_none()
    if not inv or (inv.expires_at and inv.expires_at < datetime.utcnow()):
        return None
    # Ссылки на роль одноразовые; ссылку водителя можно открыть повторно (тот же водитель/сменщик)
    if inv.kind != "driver" and inv.used_by:
        return None
    return inv


def invite_link(bot_username: str, prefix: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start={prefix}_{code}"


# ==================== ССЫЛКА НА КАРТУ МАРШРУТА ====================

def track_sig(trip_id: int) -> str:
    key = settings.telegram_bot_token.encode()
    return hmac.new(key, f"track:{trip_id}".encode(), hashlib.sha256).hexdigest()[:20]


def track_url(trip_id: int) -> Optional[str]:
    base = (settings.telegram_webhook_url or "").rstrip("/")
    if not base:
        return None
    return f"{base}/track/{trip_id}/{track_sig(trip_id)}"
