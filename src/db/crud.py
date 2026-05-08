"""
CRUD операции для работы с базой данных.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from src.db.models import Driver, Trip, Location, DriverRegistration


# ==================== DRIVERS ====================

async def get_driver_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[Driver]:
    """Получить водителя по Telegram ID"""
    result = await session.execute(
        select(Driver).where(Driver.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_driver_by_truck_number(session: AsyncSession, truck_number: str) -> Optional[Driver]:
    """Получить водителя по номеру машины"""
    result = await session.execute(
        select(Driver).where(
            and_(
                Driver.truck_number == truck_number.upper(),
                Driver.is_active == True
            )
        )
    )
    return result.scalar_one_or_none()


async def create_driver(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> Driver:
    """Создать нового водителя"""
    driver = Driver(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )
    session.add(driver)
    await session.flush()
    logger.info(f"Created new driver: {telegram_id}")
    return driver


async def update_driver_consent(
    session: AsyncSession,
    telegram_id: int,
    consent: bool
) -> Optional[Driver]:
    """Обновить согласие водителя"""
    driver = await get_driver_by_telegram_id(session, telegram_id)
    if driver:
        driver.consent_given = consent
        driver.consent_date = datetime.utcnow() if consent else None
        await session.flush()
        logger.info(f"Updated consent for driver {telegram_id}: {consent}")
    return driver


async def update_driver_transport(
    session: AsyncSession,
    telegram_id: int,
    truck_number: str,
    trailer_number: Optional[str] = None
) -> Optional[Driver]:
    """Обновить данные транспорта водителя"""
    driver = await get_driver_by_telegram_id(session, telegram_id)
    if driver:
        driver.truck_number = truck_number.upper().replace(" ", "")
        driver.trailer_number = trailer_number.upper().replace(" ", "") if trailer_number else None
        driver.updated_at = datetime.utcnow()
        await session.flush()
        logger.info(f"Updated transport for driver {telegram_id}: {truck_number}")
    return driver


async def get_active_drivers(session: AsyncSession) -> List[Driver]:
    """Получить всех активных водителей с согласием"""
    result = await session.execute(
        select(Driver).where(
            and_(
                Driver.is_active == True,
                Driver.consent_given == True
            )
        )
    )
    return result.scalars().all()


# ==================== TRIPS ====================

async def create_trip(
    session: AsyncSession,
    driver_id: int,
    truck_number: str,
    trailer_number: Optional[str] = None,
    bitrix_deal_id: Optional[int] = None,
    **kwargs
) -> Trip:
    """Создать новый рейс"""
    trip = Trip(
        driver_id=driver_id,
        truck_number=truck_number.upper(),
        trailer_number=trailer_number.upper() if trailer_number else None,
        bitrix_deal_id=bitrix_deal_id,
        **kwargs
    )
    session.add(trip)
    await session.flush()
    logger.info(f"Created trip for driver {driver_id}: {truck_number}")
    return trip


async def get_active_trip_by_truck(session: AsyncSession, truck_number: str) -> Optional[Trip]:
    """Получить активный рейс по номеру машины"""
    result = await session.execute(
        select(Trip).where(
            and_(
                Trip.truck_number == truck_number.upper(),
                Trip.status == "active"
            )
        ).order_by(Trip.created_at.desc())
    )
    return result.scalar_one_or_none()


async def get_active_trip_by_driver(session: AsyncSession, driver_id: int) -> Optional[Trip]:
    """Получить активный рейс водителя"""
    result = await session.execute(
        select(Trip).where(
            and_(
                Trip.driver_id == driver_id,
                Trip.status == "active"
            )
        ).order_by(Trip.created_at.desc())
    )
    return result.scalar_one_or_none()


async def update_trip_from_bitrix(
    session: AsyncSession,
    trip_id: int,
    **kwargs
) -> Optional[Trip]:
    """Обновить данные рейса из Битрикс24"""
    result = await session.execute(
        select(Trip).where(Trip.id == trip_id)
    )
    trip = result.scalar_one_or_none()
    if trip:
        for key, value in kwargs.items():
            if hasattr(trip, key):
                setattr(trip, key, value)
        trip.updated_at = datetime.utcnow()
        await session.flush()
    return trip


async def complete_trip(session: AsyncSession, trip_id: int) -> Optional[Trip]:
    """Завершить рейс"""
    result = await session.execute(
        select(Trip).where(Trip.id == trip_id)
    )
    trip = result.scalar_one_or_none()
    if trip:
        trip.status = "completed"
        trip.completed_at = datetime.utcnow()
        await session.flush()
        logger.info(f"Trip {trip_id} completed")
    return trip


async def get_trips_for_daily_check(session: AsyncSession) -> List[Trip]:
    """Получить активные рейсы для ежедневной проверки"""
    result = await session.execute(
        select(Trip).where(Trip.status == "active")
    )
    return result.scalars().all()


# ==================== LOCATIONS ====================

async def save_location(
    session: AsyncSession,
    driver_id: int,
    latitude: float,
    longitude: float,
    address: Optional[str] = None,
    trip_id: Optional[int] = None,
    distance_to_destination: Optional[float] = None,
) -> Location:
    """Сохранить геолокацию водителя"""
    location = Location(
        driver_id=driver_id,
        trip_id=trip_id,
        latitude=latitude,
        longitude=longitude,
        address=address,
        distance_to_destination_km=distance_to_destination,
    )
    session.add(location)
    await session.flush()
    logger.info(f"Saved location for driver {driver_id}: ({latitude}, {longitude})")
    return location


async def get_last_location(session: AsyncSession, driver_id: int) -> Optional[Location]:
    """Получить последнюю локацию водителя"""
    result = await session.execute(
        select(Location)
        .where(Location.driver_id == driver_id)
        .order_by(Location.recorded_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_locations_for_trip(session: AsyncSession, trip_id: int) -> List[Location]:
    """Получить все локации для рейса"""
    result = await session.execute(
        select(Location)
        .where(Location.trip_id == trip_id)
        .order_by(Location.recorded_at.asc())
    )
    return result.scalars().all()


async def mark_location_synced(
    session: AsyncSession,
    location_id: int,
    bitrix_deal_id: int
):
    """Отметить локацию как синхронизированную с Битрикс24"""
    await session.execute(
        update(Location)
        .where(Location.id == location_id)
        .values(
            synced_to_bitrix=True,
            synced_at=datetime.utcnow(),
            bitrix_deal_id=bitrix_deal_id
        )
    )


# ==================== DRIVER REGISTRATIONS ====================

async def create_driver_registration(
    session: AsyncSession,
    telegram_id: int,
    truck_number: str,
    trailer_number: Optional[str] = None,
) -> DriverRegistration:
    """Создать регистрацию водителя (до появления сделки)"""
    # Проверяем, нет ли уже активной регистрации
    existing = await session.execute(
        select(DriverRegistration).where(
            and_(
                DriverRegistration.truck_number == truck_number.upper(),
                DriverRegistration.status == "waiting"
            )
        )
    )
    existing_reg = existing.scalar_one_or_none()
    
    if existing_reg:
        # Обновляем существующую
        existing_reg.telegram_id = telegram_id
        existing_reg.trailer_number = trailer_number.upper() if trailer_number else None
        existing_reg.updated_at = datetime.utcnow()
        await session.flush()
        return existing_reg
    
    # Создаём новую
    registration = DriverRegistration(
        telegram_id=telegram_id,
        truck_number=truck_number.upper(),
        trailer_number=trailer_number.upper() if trailer_number else None,
        expires_at=datetime.utcnow() + timedelta(days=30),  # Автоочистка через 30 дней
    )
    session.add(registration)
    await session.flush()
    logger.info(f"Created driver registration: {truck_number}")
    return registration


async def find_waiting_registration(
    session: AsyncSession,
    truck_number: str
) -> Optional[DriverRegistration]:
    """Найти ожидающую регистрацию по номеру машины"""
    result = await session.execute(
        select(DriverRegistration).where(
            and_(
                DriverRegistration.truck_number == truck_number.upper(),
                DriverRegistration.status == "waiting"
            )
        )
    )
    return result.scalar_one_or_none()


async def match_registration_with_deal(
    session: AsyncSession,
    truck_number: str,
    deal_id: int
) -> Optional[DriverRegistration]:
    """Сопоставить регистрацию со сделкой"""
    registration = await find_waiting_registration(session, truck_number)
    if registration:
        registration.status = "matched"
        registration.matched_deal_id = deal_id
        registration.matched_at = datetime.utcnow()
        await session.flush()
        logger.info(f"Matched registration {truck_number} with deal {deal_id}")
    return registration


async def update_registration_location(
    session: AsyncSession,
    registration_id: int,
    latitude: float,
    longitude: float,
    address: Optional[str] = None
):
    """Обновить последнюю локацию в регистрации"""
    await session.execute(
        update(DriverRegistration)
        .where(DriverRegistration.id == registration_id)
        .values(
            last_lat=latitude,
            last_lon=longitude,
            last_address=address,
            last_location_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    )
