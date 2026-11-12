"""
Уведомления админам (ADMIN_IDS) о событиях бота.

Типы событий (можно отключать из админки, хранится в app_settings):
  reg      — новая регистрация водителя
  match    — рейс привязан к сделке
  silence  — водитель молчит дольше SILENCE_HOURS
  lastcall — сработал last call (близко к терминалу / долго в пути)
  done     — рейс завершён
  error    — ошибки синхронизации с Битрикс24
  digest   — утренняя сводка
"""

import asyncio
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from loguru import logger

from src.config import get_settings

settings = get_settings()

EVENT_TITLES = {
    "reg": "Новые регистрации",
    "match": "Привязка к сделке",
    "silence": "Водитель молчит",
    "lastcall": "Last call",
    "done": "Завершение рейса",
    "error": "Ошибки Битрикс24",
    "digest": "Утренняя сводка",
}

_bot: Optional[Bot] = None


def set_notify_bot(bot: Bot):
    global _bot
    _bot = bot


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


async def event_enabled(event: str) -> bool:
    from src.db.database import get_session
    from src.db import crud
    try:
        async with get_session() as session:
            return (await crud.get_setting(session, f"notify_{event}", "1")) == "1"
    except Exception as e:
        logger.warning(f"Cannot read notify setting {event}: {e}")
        return True


async def notify_admins(
    event: str,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
):
    """Отправить уведомление всем админам, если тип события включён. Ошибки не пробрасывает."""
    if not _bot or not settings.admin_ids:
        return
    try:
        if not await event_enabled(event):
            return
    except Exception:
        pass
    for admin_id in settings.admin_ids:
        try:
            await _bot.send_message(
                admin_id, text, reply_markup=reply_markup,
                parse_mode="HTML", disable_web_page_preview=True,
            )
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")


def fire(event: str, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Отправить уведомление в фоне, не задерживая ответ водителю."""
    try:
        asyncio.get_running_loop().create_task(notify_admins(event, text, reply_markup))
    except RuntimeError:
        pass
