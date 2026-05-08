"""
Главный модуль приложения.
Запуск Telegram бота + FastAPI сервера.
"""

import asyncio
import sys
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI
import uvicorn
from loguru import logger

from src.config import get_settings
from src.db.database import init_db, close_db
from src.bot import router as bot_router, keyboards
from src.api import router as api_router, set_bot_and_dispatcher
from src.services.scheduler import start_scheduler, stop_scheduler, set_bot_instance

# Конфигурация
settings = get_settings()

# Настройка логирования
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level,
    colorize=True
)

# Глобальные объекты
bot: Bot = None
dp: Dispatcher = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для FastAPI"""
    global bot, dp
    
    logger.info("Starting application...")
    
    # Инициализация базы данных
    await init_db()
    
    # Создание бота
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создание диспетчера с Redis storage для FSM
    try:
        storage = RedisStorage.from_url(settings.redis_url)
        logger.info("Using Redis storage for FSM")
    except Exception as e:
        logger.warning(f"Redis not available, using memory storage: {e}")
        from aiogram.fsm.storage.memory import MemoryStorage
        storage = MemoryStorage()
    
    dp = Dispatcher(storage=storage)
    dp.include_router(bot_router)
    
    # Установка бота для webhooks API
    set_bot_and_dispatcher(bot, dp)
    
    # Установка бота для планировщика
    set_bot_instance(bot, keyboards)
    
    # Настройка webhook (если указан URL)
    if settings.telegram_webhook_url:
        webhook_url = f"{settings.telegram_webhook_url.rstrip('/')}/webhook/telegram"
        await bot.set_webhook(webhook_url)
        logger.info(f"Webhook set: {webhook_url}")
    else:
        # Long polling режим (для разработки)
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted, using long polling")
    
    # Запуск планировщика
    start_scheduler()
    
    logger.info("Application started successfully!")
    
    yield
    
    # Завершение работы
    logger.info("Shutting down application...")
    
    stop_scheduler()
    
    if settings.telegram_webhook_url:
        await bot.delete_webhook()
    
    await bot.session.close()
    await close_db()
    
    logger.info("Application stopped")


# Создание FastAPI приложения
app = FastAPI(
    title="Driver Tracking Bot",
    description="Telegram бот для отслеживания водителей с интеграцией Битрикс24",
    version="1.0.0",
    lifespan=lifespan
)

# Подключение API роутера
app.include_router(api_router)


async def start_polling():
    """Запуск бота в режиме long polling (для разработки)"""
    global bot, dp
    
    logger.info("Starting bot polling...")
    
    # Инициализация базы данных
    await init_db()
    
    # Создание бота
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создание диспетчера
    try:
        storage = RedisStorage.from_url(settings.redis_url)
        logger.info("Using Redis storage for FSM")
    except Exception as e:
        logger.warning(f"Redis not available, using memory storage: {e}")
        from aiogram.fsm.storage.memory import MemoryStorage
        storage = MemoryStorage()
    
    dp = Dispatcher(storage=storage)
    dp.include_router(bot_router)
    
    # Установка бота для планировщика
    set_bot_instance(bot, keyboards)
    
    # Удаляем старый webhook
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск планировщика
    start_scheduler()
    
    logger.info("Bot started in polling mode")
    
    try:
        await dp.start_polling(bot)
    finally:
        stop_scheduler()
        await bot.session.close()
        await close_db()


def main():
    """Точка входа"""
    
    if settings.app_env == "development" and not settings.telegram_webhook_url:
        # Режим разработки: только polling без FastAPI
        logger.info("Running in development mode (polling only)")
        asyncio.run(start_polling())
    else:
        # Production режим: FastAPI + Webhook
        logger.info(f"Running in production mode on {settings.app_host}:{settings.app_port}")
        uvicorn.run(
            "src.main:app",
            host=settings.app_host,
            port=settings.app_port,
            reload=settings.app_debug,
            log_level=settings.log_level.lower()
        )


if __name__ == "__main__":
    main()
