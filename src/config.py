"""
Конфигурация приложения.
Загружает настройки из переменных окружения.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # === Telegram ===
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_webhook_url: str = Field("", env="TELEGRAM_WEBHOOK_URL")
    
    # === Битрикс24 ===
    bitrix24_webhook_url: str = Field(..., env="BITRIX24_WEBHOOK_URL")
    
    # Поля сделки
    bitrix_field_truck_number: str = Field("UF_CRM_1586456781744", env="BITRIX_FIELD_TRUCK_NUMBER")
    bitrix_field_truck_number_alt: str = Field("UF_CRM_67DB130DAB397", env="BITRIX_FIELD_TRUCK_NUMBER_ALT")
    bitrix_field_terminal: str = Field("UF_CRM_1711445194523", env="BITRIX_FIELD_TERMINAL")
    bitrix_field_shipment_date: str = Field("UF_CRM_1713519647288", env="BITRIX_FIELD_SHIPMENT_DATE")
    bitrix_field_planned_arrival: str = Field("UF_CRM_67DB130DBD3AC", env="BITRIX_FIELD_PLANNED_ARRIVAL")
    bitrix_field_actual_arrival: str = Field("UF_CRM_1718362421385", env="BITRIX_FIELD_ACTUAL_ARRIVAL")
    bitrix_field_days_in_transit: str = Field("UF_CRM_1714126361147", env="BITRIX_FIELD_DAYS_IN_TRANSIT")
    bitrix_field_driver_phone: str = Field("UF_CRM_1715753845", env="BITRIX_FIELD_DRIVER_PHONE")
    bitrix_field_telegram_id: str = Field("UF_CRM_66365540E721C", env="BITRIX_FIELD_TELEGRAM_ID")
    bitrix_field_telegram_group: str = Field("UF_CRM_A_T_GROUP_ID", env="BITRIX_FIELD_TELEGRAM_GROUP")
    
    # Стадии сделки
    bitrix_stage_cargo_sent: str = Field("UC_SDO64X", env="BITRIX_STAGE_CARGO_SENT")
    bitrix_stage_cargo_arrived: str = Field("9", env="BITRIX_STAGE_CARGO_ARRIVED")
    bitrix_final_stages: List[str] = Field(
        default=["WON", "9", "UC_9G2PZA"],
        env="BITRIX_FINAL_STAGES"
    )
    
    # === Геокодирование (LocationIQ - бесплатно 5000 req/day) ===
    locationiq_api_key: str = Field("", env="LOCATIONIQ_API_KEY")
    
    # === База данных ===
    database_url: str = Field(..., env="DATABASE_URL")
    
    @property
    def async_database_url(self) -> str:
        """Convert DATABASE_URL to async-compatible URL for asyncpg."""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url
    
    # === Redis ===
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    
    # === Приложение ===
    app_env: str = Field("development", env="APP_ENV")
    app_debug: bool = Field(False, env="APP_DEBUG")
    app_host: str = Field("0.0.0.0", env="APP_HOST")
    app_port: int = Field(8000, env="PORT")
    
    # === Расписание ===
    daily_location_request_hour: int = Field(5, env="DAILY_LOCATION_REQUEST_HOUR")
    daily_location_request_minute: int = Field(0, env="DAILY_LOCATION_REQUEST_MINUTE")
    
    # === Last Call триггеры ===
    last_call_distance_km: int = Field(200, env="LAST_CALL_DISTANCE_KM")
    last_call_days_in_transit: int = Field(5, env="LAST_CALL_DAYS_IN_TRANSIT")
    
    # === Логирование ===
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Справочник терминалов
TERMINALS = {
    "86": {
        "code": "Коломна",
        "name_en": 'SVH OOO "SEVERNAYA ZVEZDA A & P"',
        "name_ru": 'СВХ ООО "Северная звезда А&П"',
        "address_en": "Moscow region, Kolomna, Avtomobilistov proezd, 8",
        "address_ru": "Московская область, г. Коломна, проезд Автомобилистов, д. 8",
        "lat": 55.116124,
        "lon": 38.730962,
        "google_maps": "https://goo.gl/maps/6Pb4oeUxTBrcSTWq5",
        "yandex_maps": "https://yandex.ru/maps/-/CCUaBMf4lD",
    },
}


@lru_cache()
def get_settings() -> Settings:
    """Получить настройки (с кэшированием)"""
    return Settings()
