"""Подставляет в обработчики параметр lang — язык пользователя."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from src.i18n import get_lang


class LangMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user:
            data["lang"] = await get_lang(user.id, user.language_code)
        else:
            data["lang"] = "ru"
        return await handler(event, data)
