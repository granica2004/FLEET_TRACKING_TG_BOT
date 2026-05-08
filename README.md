# 🚛 Driver Tracking Bot

Telegram-бот для отслеживания геолокации водителей с интеграцией Битрикс24 CRM.

## 📋 Возможности

- ✅ Регистрация водителей через Telegram
- 📍 Отслеживание геолокации с записью в Битрикс24
- 🔄 Автоматическое сопоставление водителей со сделками
- 📅 Ежедневный запрос местоположения
- 🏁 Last Call механизм (уведомление при приближении к терминалу)
- 🏭 Справочник терминалов с адресами и координатами
- 📊 Webhook для синхронизации с Битрикс24

## 🛠️ Технологический стек

- **Python 3.11+**
- **aiogram 3.x** — Telegram Bot API
- **FastAPI** — Webhooks и REST API
- **PostgreSQL** — База данных
- **Redis** — FSM Storage и кэширование
- **APScheduler** — Планировщик задач
- **LocationIQ / Nominatim** — Геокодирование (бесплатно)
- **OSRM** — Routing и маршруты (бесплатно)

## 🚀 Быстрый старт

### Локальная разработка (Docker Compose)

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd driver-tracking-bot

# 2. Скопировать и настроить .env
cp .env.example .env
nano .env  # Заполнить токены

# 3. Запустить с Docker Compose
docker-compose up -d

# 4. Проверить логи
docker-compose logs -f bot
```

### Деплой на Railway

1. Создайте новый проект на [Railway](https://railway.com)
2. Подключите GitHub репозиторий
3. Добавьте PostgreSQL плагин
4. Добавьте Redis плагин
5. Настройте переменные окружения (см. `.env.example`)
6. Railway автоматически задеплоит приложение

```bash
# Или через CLI
railway init
railway add --plugin postgresql
railway add --plugin redis
railway up
```

### Переменные окружения

```env
# Обязательные
TELEGRAM_BOT_TOKEN=your_bot_token
BITRIX24_WEBHOOK_URL=https://your-domain.bitrix24.ru/rest/1/token/
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Опциональные
REDIS_URL=redis://localhost:6379/0
YANDEX_GEOCODER_API_KEY=your_key
TELEGRAM_WEBHOOK_URL=https://your-app.up.railway.app
```

## 📱 Использование бота

### Для водителя

1. Открыть бота в Telegram
2. Нажать `/start`
3. Дать согласие на передачу геолокации
4. Ввести номер тягача
5. Ввести номер прицепа (или `-` если нет)
6. Отправлять геолокацию по запросу

### Кнопки бота

- 📍 **Отправить местоположение** — отправка текущей геолокации
- 📝 **Уведомить о прибытии** — указать планируемую дату прибытия
- 🏭 **Адрес терминала** — получить адрес и точку на карте
- 🔄 **Новая перевозка** — начать отслеживание нового рейса
- ❌ **Завершить текущую** — остановить отслеживание

## ⚙️ Настройка Битрикс24

### 1. Создание Webhook

В Битрикс24 перейдите: **Приложения → Разработчикам → Другое → Входящий вебхук**

Необходимые разрешения:
- `crm` — Работа с CRM
- `user` — Информация о пользователях

### 2. Настройка исходящего Webhook

Для автоматического уведомления бота об изменениях сделок:

**CRM → Настройки → Автоматизация → Роботы**

Создайте робота "Webhook" на событие "Изменение сделки" с URL:
```
https://your-app.up.railway.app/webhook/bitrix24/deal-update
```

### 3. Пользовательские поля сделки

Бот использует следующие поля (настраиваются в `.env`):

| Поле | Описание | По умолчанию |
|------|----------|--------------|
| `UF_CRM_1586456781744` | Номер т/с | Основное поле |
| `UF_CRM_67DB130DAB397` | Номер машины/прицепа | Альтернативное |
| `UF_CRM_1711445194523` | Терминал | Enumeration |
| `UF_CRM_66365540E721C` | Telegram ID водителя | String |

## 📁 Структура проекта


```
driver-tracking-bot/
├── src/
│   ├── __init__.py
│   ├── main.py              # Точка входа
│   ├── config.py            # Конфигурация
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py      # Обработчики команд
│   │   ├── keyboards.py     # Клавиатуры
│   │   └── states.py        # FSM состояния
│   ├── api/
│   │   ├── __init__.py
│   │   └── webhooks.py      # FastAPI эндпоинты
│   ├── services/
│   │   ├── __init__.py
│   │   ├── bitrix.py        # Клиент Битрикс24
│   │   ├── geocoder.py      # Геокодирование
│   │   └── scheduler.py     # Планировщик
│   └── db/
│       ├── __init__.py
│       ├── database.py      # Подключение к БД
│       ├── models.py        # SQLAlchemy модели
│       └── crud.py          # CRUD операции
├── alembic/                 # Миграции БД
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── railway.toml
├── .env.example
└── README.md
```

## 🗄️ База данных

### Таблицы

- **drivers** — Водители (Telegram ID, номер машины, согласие)
- **trips** — Рейсы (связь водитель-сделка, маршрут, даты)
- **locations** — История геолокаций
- **driver_registrations** — Ожидающие сопоставления (до создания сделки)

### Миграции

```bash
# Создать миграцию
alembic revision --autogenerate -m "description"

# Применить миграции
alembic upgrade head
```

## 🔧 API Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/health` | Health check |
| POST | `/webhook/telegram` | Telegram webhook |
| POST | `/webhook/bitrix24/deal-update` | Битрикс24 webhook |
| GET | `/api/drivers/{telegram_id}` | Информация о водителе |
| POST | `/api/notify/{telegram_id}` | Отправить уведомление |

## 📊 Мониторинг

### Логи

```bash
# Docker
docker-compose logs -f bot

# Railway
railway logs
```

### Метрики

Доступны через endpoint `/health`:
```json
{
  "status": "ok",
  "timestamp": "2026-03-15T10:30:00",
  "service": "driver-tracking-bot"
}
```

## 🔒 Безопасность

- Все API ключи хранятся в переменных окружения
- Согласие водителя на передачу геолокации обязательно
- Данные о местоположении передаются только связанному брокеру
- HTTPS обязателен для webhook

## 🐛 Troubleshooting

### Бот не отвечает

1. Проверьте `TELEGRAM_BOT_TOKEN`
2. Проверьте логи: `docker-compose logs bot`
3. Убедитесь, что webhook настроен правильно

### Сделка не находится

1. Проверьте номер машины в Битрикс24
2. Убедитесь, что поле `UF_CRM_1586456781744` заполнено
3. Проверьте, что сделка не закрыта (`CLOSED = N`)

### Геокодирование не работает

1. Проверьте `YANDEX_GEOCODER_API_KEY`
2. Проверьте лимиты API Яндекс.Карт
3. Бот продолжит работу, показывая только координаты

## 📞 Контакты

- **Разработка:** [ваш контакт]
- **Поддержка Битрикс24:** [контакт]

## 📄 Лицензия

MIT
