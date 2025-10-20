FROM python:3.11-slim-bullseye

# Устанавливаем системные зависимости для OpenCV, MediaPipe и других библиотек
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libatlas-base-dev \
    python3-dev \
    python3-numpy \
    libtbb2 \
    libtbb-dev \
    libdc1394-22-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости сначала для кэширования
COPY requirements.txt .

# Устанавливаем Python пакеты с оптимизацией для TensorFlow
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

# Добавляем healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from bot.database.session import engine; asyncio.run(engine.connect())" || exit 1

# Команда запуска бота
CMD ["python", "-m", "bot.main"]