"""
Общая логика рейсов: перенос данных сделки в рейс, форматирование для показа.
"""

from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, Optional

from dateutil import parser as dtparser

from src.config import get_settings, TERMINALS, terminal_name

settings = get_settings()


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = dtparser.isoparse(str(value))
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def deal_trip_fields(deal: Dict[str, Any]) -> Dict[str, Any]:
    """Поля рейса из сделки Битрикс24."""
    terminal_code = deal.get(settings.bitrix_field_terminal) or None
    if terminal_code is not None:
        terminal_code = str(terminal_code)
    t = TERMINALS.get(terminal_code or "", {})
    return {
        "bitrix_deal_id": int(deal["ID"]),
        "bitrix_deal_title": deal.get("TITLE"),
        "bitrix_stage_id": deal.get("STAGE_ID"),
        "terminal_code": terminal_code,
        "destination_address": t.get("address_ru"),
        "destination_lat": t.get("lat"),
        "destination_lon": t.get("lon"),
        "shipment_date": _parse_dt(deal.get(settings.bitrix_field_shipment_date)),
        "planned_arrival_date": _parse_dt(deal.get(settings.bitrix_field_planned_arrival)),
    }


def apply_deal_to_trip(trip, deal: Dict[str, Any]):
    """Привязать существующий рейс к сделке (без коммита)."""
    for key, value in deal_trip_fields(deal).items():
        if value is None and key in ("shipment_date", "planned_arrival_date") and getattr(trip, key):
            continue  # не затираем известную дату пустой
        setattr(trip, key, value)
    trip.updated_at = datetime.utcnow()


def ago(dt: Optional[datetime]) -> str:
    """«5 мин назад», «3 ч назад», «2 дн назад»."""
    if not dt:
        return "—"
    sec = int((datetime.utcnow() - dt).total_seconds())
    if sec < 60:
        return "только что"
    if sec < 3600:
        return f"{sec // 60} мин назад"
    if sec < 86400:
        return f"{sec // 3600} ч назад"
    return f"{sec // 86400} дн назад"


def msk(dt: Optional[datetime], fmt: str = "%d.%m %H:%M") -> str:
    if not dt:
        return "—"
    from datetime import timedelta
    return (dt + timedelta(hours=3)).strftime(fmt)


def driver_label(driver) -> str:
    if not driver:
        return "водитель не найден"
    name = " ".join(x for x in [driver.first_name, driver.last_name] if x) or "Без имени"
    name = escape(name)
    if driver.username:
        name += f" @{escape(driver.username)}"
    return name


def deal_link(deal_id: Optional[int], title: Optional[str] = None) -> str:
    if not deal_id:
        return "⚠️ не привязан к сделке"
    label = f"#{deal_id}" + (f" {escape(title)}" if title else "")
    return f'<a href="{settings.deal_url(deal_id)}">{label}</a>'


__all__ = [
    "deal_trip_fields", "apply_deal_to_trip", "ago", "msk",
    "driver_label", "deal_link", "terminal_name",
]
