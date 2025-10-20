FROM python:3.11-slim-bullseye

# Установка системных зависимостей для сборки greenlet, asyncpg и других библиотек
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости для кэширования слоев
COPY requirements.txt .

# Обновляем pip и устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы проекта
COPY . .

# Создаем необходимые каталоги
RUN mkdir -p data logs

# Создаем пользователя для запуска приложения
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app
USER botuser

# Добавляем healthcheck (пример)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from bot.database.session import engine; asyncio.run(engine.connect())" || exit 1

# Команда запуска
CMD ["python", "-m", "bot.main"]
