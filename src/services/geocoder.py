"""
Сервис геокодирования и работы с картами.
Использует LocationIQ (основной) + Nominatim (fallback).
Оба сервиса бесплатные и используют данные OpenStreetMap.

LocationIQ: 5000 запросов/день бесплатно
Nominatim: бесплатно, но 1 req/sec и требует User-Agent
"""

import httpx
from typing import Optional, Tuple, Dict, Any
from math import radians, sin, cos, sqrt, atan2
from loguru import logger

from src.config import get_settings, TERMINALS

settings = get_settings()


class GeocoderService:
    """
    Сервис обратного геокодирования (координаты -> адрес).
    
    Приоритет:
    1. LocationIQ (5000 req/day бесплатно)
    2. Nominatim (бесплатно, но 1 req/sec)
    """
    
    LOCATIONIQ_URL = "https://us1.locationiq.com/v1/reverse"
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
    
    def __init__(self, api_key: Optional[str] = None):
        self.locationiq_key = api_key or settings.locationiq_api_key
        self.timeout = httpx.Timeout(10.0)
        self.user_agent = "DriverTrackingBot/1.0 (Telegram bot for logistics)"
    
    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Получить адрес по координатам.
        Сначала пробует LocationIQ, при неудаче — Nominatim.
        """
        # Пробуем LocationIQ (если есть ключ)
        if self.locationiq_key:
            address = await self._locationiq_reverse(latitude, longitude)
            if address:
                return address
        
        # Fallback на Nominatim (всегда бесплатный)
        address = await self._nominatim_reverse(latitude, longitude)
        if address:
            return address
        
        # Если всё не сработало — возвращаем координаты
        return f"Координаты: {latitude:.6f}, {longitude:.6f}"
    
    async def _locationiq_reverse(self, lat: float, lon: float) -> Optional[str]:
        """Обратное геокодирование через LocationIQ"""
        params = {
            "key": self.locationiq_key,
            "lat": lat,
            "lon": lon,
            "format": "json",
            "accept-language": "ru"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.LOCATIONIQ_URL, params=params)
                response.raise_for_status()
                data = response.json()
                
                address = data.get("display_name")
                if address:
                    logger.debug(f"LocationIQ: ({lat}, {lon}) -> {address[:50]}...")
                    return address
                
                return None
                
        except Exception as e:
            logger.warning(f"LocationIQ error: {e}")
            return None
    
    async def _nominatim_reverse(self, lat: float, lon: float) -> Optional[str]:
        """Обратное геокодирование через Nominatim (fallback)"""
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "accept-language": "ru",
            "zoom": 18  # Уровень детализации адреса
        }
        
        headers = {
            "User-Agent": self.user_agent
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.NOMINATIM_URL, 
                    params=params, 
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                
                address = data.get("display_name")
                if address:
                    logger.debug(f"Nominatim: ({lat}, {lon}) -> {address[:50]}...")
                    return address
                
                return None
                
        except Exception as e:
            logger.warning(f"Nominatim error: {e}")
            return None
    
    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Получить координаты по адресу (прямое геокодирование).
        """
        # Пробуем LocationIQ
        if self.locationiq_key:
            coords = await self._locationiq_forward(address)
            if coords:
                return coords
        
        # Fallback на Nominatim
        return await self._nominatim_forward(address)
    
    async def _locationiq_forward(self, address: str) -> Optional[Tuple[float, float]]:
        """Прямое геокодирование через LocationIQ"""
        url = "https://us1.locationiq.com/v1/search"
        params = {
            "key": self.locationiq_key,
            "q": address,
            "format": "json",
            "limit": 1
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data and len(data) > 0:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    return (lat, lon)
                
                return None
                
        except Exception as e:
            logger.warning(f"LocationIQ forward error: {e}")
            return None
    
    async def _nominatim_forward(self, address: str) -> Optional[Tuple[float, float]]:
        """Прямое геокодирование через Nominatim"""
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": self.user_agent}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if data and len(data) > 0:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    return (lat, lon)
                
                return None
                
        except Exception as e:
            logger.warning(f"Nominatim forward error: {e}")
            return None


class MapsService:
    """
    Сервис для работы с картами и маршрутами.
    Использует OSRM (бесплатный routing на базе OSM).
    """
    
    # OSRM — бесплатный routing сервис
    OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
    
    def __init__(self, geocoder_api_key: Optional[str] = None):
        self.geocoder = GeocoderService(geocoder_api_key)
        self.timeout = httpx.Timeout(15.0)
    
    @staticmethod
    def haversine_distance(
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """
        Расчёт расстояния по формуле Хаверсина (по прямой).
        Бесплатно, без API.
        
        Returns:
            Расстояние в километрах
        """
        R = 6371  # Радиус Земли в км
        
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    async def calculate_route(
        self,
        from_lat: float, from_lon: float,
        to_lat: float, to_lon: float
    ) -> Dict[str, Any]:
        """
        Расчёт маршрута через OSRM (бесплатный сервис на базе OpenStreetMap).
        
        Returns:
            Словарь с distance_km, duration_minutes, eta_text
        """
        # Сначала пробуем OSRM
        osrm_result = await self._osrm_route(from_lat, from_lon, to_lat, to_lon)
        if osrm_result:
            return osrm_result
        
        # Fallback на формулу Хаверсина
        distance = self.haversine_distance(from_lat, from_lon, to_lat, to_lon)
        # Примерная скорость 55 км/ч для грузовика (учитываем трафик и дороги)
        duration_hours = distance / 55
        return {
            "distance_km": distance,
            "duration_minutes": int(duration_hours * 60),
            "eta_text": self._format_duration(int(duration_hours * 3600)),
            "source": "haversine"
        }
    
    async def _osrm_route(
        self,
        from_lat: float, from_lon: float,
        to_lat: float, to_lon: float
    ) -> Optional[Dict[str, Any]]:
        """Расчёт маршрута через OSRM"""
        # OSRM принимает координаты как lon,lat (не lat,lon!)
        url = f"{self.OSRM_URL}/{from_lon},{from_lat};{to_lon},{to_lat}"
        params = {
            "overview": "false",  # Не нужна геометрия маршрута
            "alternatives": "false"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                
                if response.status_code != 200:
                    logger.warning(f"OSRM returned status {response.status_code}")
                    return None
                
                data = response.json()
                
                if data.get("code") != "Ok":
                    logger.warning(f"OSRM error: {data.get('code')}")
                    return None
                
                routes = data.get("routes", [])
                if not routes:
                    return None
                
                route = routes[0]
                distance_m = route.get("distance", 0)  # метры
                duration_s = route.get("duration", 0)  # секунды
                
                return {
                    "distance_km": distance_m / 1000,
                    "duration_minutes": int(duration_s / 60),
                    "eta_text": self._format_duration(int(duration_s)),
                    "source": "osrm"
                }
                
        except Exception as e:
            logger.warning(f"OSRM error: {e}")
            return None
    
    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Форматирование времени в пути"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        if hours > 24:
            days = hours // 24
            hours = hours % 24
            return f"{days} д. {hours} ч."
        elif hours > 0:
            return f"{hours} ч. {minutes} мин."
        else:
            return f"{minutes} мин."
    
    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[str]:
        """Обратное геокодирование (делегируем в GeocoderService)"""
        return await self.geocoder.reverse_geocode(latitude, longitude)
    
    def get_terminal_info(self, terminal_code: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о терминале из справочника"""
        return TERMINALS.get(terminal_code)
    
    def get_terminal_coordinates(self, terminal_code: str) -> Optional[Tuple[float, float]]:
        """Получить координаты терминала"""
        terminal = self.get_terminal_info(terminal_code)
        if terminal:
            return (terminal["lat"], terminal["lon"])
        return None
    
    async def get_distance_to_terminal(
        self,
        from_lat: float, from_lon: float,
        terminal_code: str
    ) -> Optional[Dict[str, Any]]:
        """Расчёт расстояния до терминала"""
        terminal_coords = self.get_terminal_coordinates(terminal_code)
        if not terminal_coords:
            return None
        
        return await self.calculate_route(
            from_lat, from_lon,
            terminal_coords[0], terminal_coords[1]
        )


# Глобальные экземпляры
geocoder = GeocoderService()
maps_service = MapsService()
