"""Привязка Telegram-webhook.

Продакшен не вызывает deleteWebhook при остановке. Railway гасит старый
контейнер уже после старта нового, и shutdown старого снимал вебхук,
который новый процесс только что поставил. Команды после этого не доходят,
хотя процесс жив и сам шлёт сообщения (планировщик).
"""

from __future__ import annotations

import asyncio

from loguru import logger

# Второй заход — после того, как предыдущий контейнер успеет завершиться.
REASSERT_DELAYS_SEC = (30, 180)


def webhook_url_for(base: str) -> str:
    return f"{base.rstrip('/')}/webhook/telegram"


async def bind_webhook(bot, base: str):
    """Поставить вебхук и записать, что Telegram реально сохранил."""
    url = webhook_url_for(base)
    await bot.set_webhook(url)
    info = await bot.get_webhook_info()
    logger.info(
        f"Webhook bound: url={info.url} pending={info.pending_update_count} "
        f"last_error={info.last_error_message!r}"
    )
    if info.url != url:
        logger.error(f"Webhook URL mismatch: expected {url}, got {info.url!r}")
    return info


async def reassert_webhook(bot, base: str, delays=REASSERT_DELAYS_SEC) -> None:
    """Повторить привязку, если старый контейнер снял вебхук при остановке."""
    try:
        for delay in delays:
            await asyncio.sleep(delay)
            await bind_webhook(bot, base)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception(f"Webhook reassert failed: {e}")
