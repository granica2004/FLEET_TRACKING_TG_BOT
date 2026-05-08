# Dockerfile для деплоя на собственный сервер
# Railway использует Nixpacks, но этот Dockerfile пригодится для VPS

FROM python:3.11-slim

# Системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Порт для FastAPI (webhooks от Битрикс24 и Telegram)
EXPOSE 8000

# Запуск
CMD ["python", "-m", "src.main"]
