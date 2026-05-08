"""
Клиент для работы с Битрикс24 REST API.
"""

import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from src.config import get_settings

settings = get_settings()


class Bitrix24Client:
    """Асинхронный клиент Битрикс24 REST API"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.base_url = (webhook_url or settings.bitrix24_webhook_url).rstrip("/")
        self.timeout = httpx.Timeout(30.0)
    
    async def _request(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Выполнить запрос к API"""
        url = f"{self.base_url}/{method}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=params or {})
                response.raise_for_status()
                data = response.json()
                
                if "error" in data:
                    logger.error(f"Bitrix24 API error: {data['error']} - {data.get('error_description', '')}")
                    raise Exception(f"Bitrix24 API error: {data['error']}")
                
                return data.get("result", data)
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP error calling Bitrix24: {e}")
                raise
    
    # ==================== СДЕЛКИ ====================
    
    async def find_deal_by_truck_number(self, truck_number: str) -> Optional[Dict[str, Any]]:
        """
        Найти активную сделку по номеру машины.
        Проверяет два поля: основное и альтернативное.
        """
        truck_clean = truck_number.upper().replace(" ", "")
        
        # Список полей для выборки
        select_fields = [
            "ID", "TITLE", "STAGE_ID", "COMPANY_ID",
            settings.bitrix_field_truck_number,
            settings.bitrix_field_truck_number_alt,
            settings.bitrix_field_terminal,
            settings.bitrix_field_shipment_date,
            settings.bitrix_field_planned_arrival,
            settings.bitrix_field_actual_arrival,
            settings.bitrix_field_days_in_transit,
            settings.bitrix_field_telegram_id,
            settings.bitrix_field_telegram_group,
        ]
        
        # Поиск по основному полю
        result = await self._request("crm.deal.list", {
            "filter": {
                settings.bitrix_field_truck_number: truck_clean,
                "CLOSED": "N"
            },
            "select": select_fields,
            "order": {"DATE_MODIFY": "DESC"}
        })
        
        if result:
            logger.info(f"Found deal by primary field: {result[0]['ID']}")
            return result[0]
        
        # Поиск по альтернативному полю
        result = await self._request("crm.deal.list", {
            "filter": {
                settings.bitrix_field_truck_number_alt: truck_clean,
                "CLOSED": "N"
            },
            "select": select_fields,
            "order": {"DATE_MODIFY": "DESC"}
        })
        
        if result:
            logger.info(f"Found deal by alt field: {result[0]['ID']}")
            return result[0]
        
        # Поиск с частичным совпадением (если номер содержит / для тягач/прицеп)
        if "/" not in truck_clean:
            result = await self._request("crm.deal.list", {
                "filter": {
                    f"%{settings.bitrix_field_truck_number}": truck_clean,
                    "CLOSED": "N"
                },
                "select": select_fields,
                "order": {"DATE_MODIFY": "DESC"}
            })
            
            if result:
                logger.info(f"Found deal by partial match: {result[0]['ID']}")
                return result[0]
        
        logger.info(f"No deal found for truck: {truck_number}")
        return None
    
    async def get_deal(self, deal_id: int) -> Optional[Dict[str, Any]]:
        """Получить сделку по ID"""
        result = await self._request("crm.deal.get", {"ID": deal_id})
        return result
    
    async def update_deal(self, deal_id: int, fields: Dict[str, Any]) -> bool:
        """Обновить поля сделки"""
        try:
            await self._request("crm.deal.update", {
                "ID": deal_id,
                "FIELDS": fields
            })
            logger.info(f"Updated deal {deal_id}: {list(fields.keys())}")
            return True
        except Exception as e:
            logger.error(f"Failed to update deal {deal_id}: {e}")
            return False
    
    async def add_timeline_comment(
        self,
        deal_id: int,
        comment: str,
    ) -> bool:
        """Добавить комментарий в таймлайн сделки"""
        try:
            await self._request("crm.timeline.comment.add", {
                "fields": {
                    "ENTITY_ID": deal_id,
                    "ENTITY_TYPE": "deal",
                    "COMMENT": comment
                }
            })
            logger.info(f"Added comment to deal {deal_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add comment to deal {deal_id}: {e}")
            return False
    
    async def add_location_comment(
        self,
        deal_id: int,
        address: str,
        latitude: float,
        longitude: float,
        distance_km: Optional[float] = None,
        eta: Optional[str] = None,
    ) -> bool:
        """Добавить комментарий с геолокацией в сделку"""
        
        # Формируем ссылку на карту
        map_url = f"https://yandex.ru/maps/?pt={longitude},{latitude}&z=15&l=map"
        
        # Формируем текст комментария
        lines = [
            "📍 <b>Местоположение водителя</b>",
            f"",
            f"🏠 Адрес: {address}",
            f"🌐 Координаты: {latitude:.6f}, {longitude:.6f}",
        ]
        
        if distance_km is not None:
            lines.append(f"📏 До назначения: {distance_km:.0f} км")
        
        if eta:
            lines.append(f"⏱️ Расчётное время: {eta}")
        
        lines.extend([
            f"",
            f"🗺️ <a href='{map_url}'>Открыть на карте</a>",
            f"",
            f"<i>Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
        ])
        
        comment = "\n".join(lines)
        return await self.add_timeline_comment(deal_id, comment)
    
    async def update_driver_telegram_id(
        self,
        deal_id: int,
        telegram_id: int,
        username: Optional[str] = None
    ) -> bool:
        """Записать Telegram ID водителя в сделку"""
        fields = {
            settings.bitrix_field_telegram_id: str(telegram_id)
        }
        # Если есть поле для username, можно добавить
        return await self.update_deal(deal_id, fields)
    
    async def update_days_in_transit(self, deal_id: int, days: int) -> bool:
        """Обновить количество дней в пути"""
        return await self.update_deal(deal_id, {
            settings.bitrix_field_days_in_transit: days
        })
    
    async def update_arrival_date(self, deal_id: int, arrival_date: datetime) -> bool:
        """Записать фактическую дату прибытия"""
        return await self.update_deal(deal_id, {
            settings.bitrix_field_actual_arrival: arrival_date.strftime("%Y-%m-%d")
        })
    
    async def is_deal_finished(self, deal_id: int) -> bool:
        """Проверить, завершена ли сделка (груз прибыл)"""
        deal = await self.get_deal(deal_id)
        if not deal:
            return True  # Сделка не найдена — считаем завершённой
        
        stage_id = deal.get("STAGE_ID", "")
        
        # Проверяем финальные стадии
        for final_stage in settings.bitrix_final_stages:
            if final_stage in stage_id:
                return True
        
        return deal.get("CLOSED") == "Y"
    
    # ==================== ТЕРМИНАЛЫ ====================
    
    async def get_terminal_from_deal(self, deal: Dict[str, Any]) -> Optional[str]:
        """Извлечь код терминала из сделки"""
        return deal.get(settings.bitrix_field_terminal)


# Глобальный экземпляр клиента
bitrix_client = Bitrix24Client()
