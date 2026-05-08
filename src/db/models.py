"""
Модели базы данных SQLAlchemy.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, 
    Float, DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Driver(Base):
    """Водитель (пользователь Telegram-бота)"""
    
    __tablename__ = "drivers"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    
    # Текущий транспорт
    truck_number = Column(String(20), nullable=True, index=True)
    trailer_number = Column(String(20), nullable=True)
    
    # Согласие на передачу геолокации
    consent_given = Column(Boolean, default=False)
    consent_date = Column(DateTime, nullable=True)
    
    # Статус
    is_active = Column(Boolean, default=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    trips = relationship("Trip", back_populates="driver", lazy="dynamic")
    locations = relationship("Location", back_populates="driver", lazy="dynamic")
    
    def __repr__(self):
        return f"<Driver {self.telegram_id} ({self.truck_number})>"


class Trip(Base):
    """Рейс/Перевозка (связь водителя со сделкой Битрикс24)"""
    
    __tablename__ = "trips"
    
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    
    # Связь с Битрикс24
    bitrix_deal_id = Column(Integer, nullable=True, index=True)
    bitrix_deal_title = Column(String(500), nullable=True)
    bitrix_stage_id = Column(String(50), nullable=True)
    
    # Транспорт (копия на момент создания рейса)
    truck_number = Column(String(20), nullable=False, index=True)
    trailer_number = Column(String(20), nullable=True)
    
    # Маршрут
    terminal_code = Column(String(50), nullable=True)
    destination_address = Column(Text, nullable=True)
    destination_lat = Column(Float, nullable=True)
    destination_lon = Column(Float, nullable=True)
    
    # Информация о грузе
    cargo_type = Column(String(100), nullable=True)
    company_name = Column(String(255), nullable=True)
    
    # Даты
    shipment_date = Column(DateTime, nullable=True)
    planned_arrival_date = Column(DateTime, nullable=True)
    actual_arrival_date = Column(DateTime, nullable=True)
    
    # Расчётные поля
    days_in_transit = Column(Integer, nullable=True)
    
    # Статус рейса
    status = Column(String(20), default="active", index=True)  # active, completed, cancelled
    last_call_triggered = Column(Boolean, default=False)
    last_call_date = Column(DateTime, nullable=True)
    
    # Telegram группа для уведомлений
    telegram_group_id = Column(String(50), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Связи
    driver = relationship("Driver", back_populates="trips")
    locations = relationship("Location", back_populates="trip", lazy="dynamic")
    
    __table_args__ = (
        Index("ix_trips_truck_status", "truck_number", "status"),
    )
    
    def __repr__(self):
        return f"<Trip {self.id} ({self.truck_number}) -> {self.terminal_code}>"


class Location(Base):
    """Геолокация водителя"""
    
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True)
    
    # Координаты
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    # Геокодированный адрес
    address = Column(Text, nullable=True)
    
    # Расстояние до цели (если известна)
    distance_to_destination_km = Column(Float, nullable=True)
    
    # Синхронизация с Битрикс24
    bitrix_deal_id = Column(Integer, nullable=True)
    synced_to_bitrix = Column(Boolean, default=False)
    synced_at = Column(DateTime, nullable=True)
    
    # Источник данных
    source = Column(String(20), default="telegram")  # telegram, manual
    
    # Метаданные
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Связи
    driver = relationship("Driver", back_populates="locations")
    trip = relationship("Trip", back_populates="locations")
    
    __table_args__ = (
        Index("ix_locations_driver_time", "driver_id", "recorded_at"),
    )
    
    def __repr__(self):
        return f"<Location {self.id} ({self.latitude}, {self.longitude})>"


class DriverRegistration(Base):
    """
    Регистрация водителя до создания сделки.
    Хранит данные водителей, для которых ещё нет сделки в Битрикс24.
    """
    
    __tablename__ = "driver_registrations"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    
    # Транспорт
    truck_number = Column(String(20), nullable=False, index=True)
    trailer_number = Column(String(20), nullable=True)
    
    # Последняя локация
    last_lat = Column(Float, nullable=True)
    last_lon = Column(Float, nullable=True)
    last_address = Column(Text, nullable=True)
    last_location_at = Column(DateTime, nullable=True)
    
    # Статус
    status = Column(String(20), default="waiting")  # waiting, matched, expired
    matched_deal_id = Column(Integer, nullable=True)
    matched_at = Column(DateTime, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Автоочистка старых записей
    
    __table_args__ = (
        Index("ix_registrations_truck_status", "truck_number", "status"),
    )
    
    def __repr__(self):
        return f"<DriverRegistration {self.truck_number} ({self.status})>"
