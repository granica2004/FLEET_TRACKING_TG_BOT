"""
FSM состояния для диалогов бота.
"""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния регистрации водителя"""
    
    # Ожидание согласия на передачу геолокации
    waiting_consent = State()
    
    # Ожидание ввода номера тягача
    waiting_truck_number = State()
    
    # Ожидание ввода номера прицепа
    waiting_trailer_number = State()
    
    # Активная перевозка
    active_trip = State()


class ArrivalStates(StatesGroup):
    """Состояния для указания даты прибытия"""
    
    # Ожидание ввода даты
    waiting_arrival_date = State()


class ManualNotificationStates(StatesGroup):
    """Состояния для ручного уведомления о прибытии"""
    
    # Ожидание подтверждения
    waiting_confirmation = State()
    
    # Ожидание комментария
    waiting_comment = State()
