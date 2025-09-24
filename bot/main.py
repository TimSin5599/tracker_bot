import logging
import asyncio

from aiogram import Dispatcher, Bot

from bot.handlers import commands
from bot.handlers.pushups import setup_pushups_handlers
from config.settings import settings
# from bot.handlers.pushups import setup_pushups_handlers
from bot.database.storage import init_database
from bot.utils.reminders import setup_reminders

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Измените на INFO вместо DEBUG
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""
    if not settings.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден! Проверьте файл .env")
        return

    logger.info("✅ Токен найден, инициализируем базу данных...")

    # Инициализируем базу данных
    await init_database()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    setup_pushups_handlers(dp)
    dp.include_router(commands.router)

    # Настраиваем напоминания
    setup_reminders(dp)
    # Запускаем бота
    logger.info("🤖 Бот запускается...")
    await dp.start_polling(bot)

    logger.info("✅ Бот запущен и работает!")
    logger.info("⏰ Напоминания настроены: 22:00 и 00:00")
    logger.info("🔍 Режим отладки включен")


if __name__ == "__main__":
    asyncio.run(main())