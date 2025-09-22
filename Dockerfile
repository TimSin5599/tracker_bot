FROM python:3.11-slim-bullseye

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости сначала для кэширования
COPY requirements.txt .

# Устанавливаем Python пакеты
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем необходимые директории
RUN mkdir -p data logs

# Создаем не-root пользователя для безопасности
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app
USER botuser

# Команда запуска бота
CMD ["python", "-m", "bot.main"]