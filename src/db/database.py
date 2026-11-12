"""
Подключение к базе данных и управление сессиями.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from loguru import logger

from src.config import get_settings
from src.db.models import Base

settings = get_settings()

# Создаём асинхронный движок
# NullPool рекомендуется для asyncio приложений
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.app_debug,
    poolclass=NullPool,
)

# Фабрика сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Инициализация базы данных (создание таблиц)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Новые колонки в существующих таблицах (create_all их не добавляет)
        if conn.dialect.name == "postgresql":
            for ddl in (
                "ALTER TABLE trips ADD COLUMN IF NOT EXISTS silence_alert_at TIMESTAMP",
                "ALTER TABLE trips ADD COLUMN IF NOT EXISTS arrived_notified_at TIMESTAMP",
                "ALTER TABLE trips ADD COLUMN IF NOT EXISTS bitrix_company_id INTEGER",
                "ALTER TABLE trips ADD COLUMN IF NOT EXISTS bitrix_contact_id INTEGER",
                "ALTER TABLE trips ADD COLUMN IF NOT EXISTS created_by_participant_id INTEGER",
                "ALTER TABLE trips ALTER COLUMN driver_id DROP NOT NULL",
                "ALTER TABLE locations ADD COLUMN IF NOT EXISTS country_code VARCHAR(5)",
                "CREATE INDEX IF NOT EXISTS ix_trips_company ON trips (bitrix_company_id)",
            ):
                await conn.execute(text(ddl))
    logger.info("Database initialized")


async def close_db():
    """Закрытие соединения с базой данных"""
    await engine.dispose()
    logger.info("Database connection closed")


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Контекстный менеджер для получения сессии БД"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def get_db() -> AsyncSession:
    """Dependency для FastAPI - получение сессии БД"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
