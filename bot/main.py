import logging
import asyncio

from aiogram import Dispatcher, Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.handlers import commands
from bot.handlers import pushups
from bot.middlewares.TopicMiddleware import TopicMiddlewares
from config.settings import settings
from bot.database.storage import init_database
# from bot.utils.reminders import setup_reminders

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
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
    scheduler = AsyncIOScheduler()
    timezone = "Europe/Moscow"
    dp.update.middleware()

    dp.update.outer_middleware(TopicMiddlewares())
    dp.include_router(commands.router)
    dp.include_router(pushups.router)

    # Настраиваем напоминания
    # setup_reminders(bot)
    # Запускаем бота
    logger.info("🤖 Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

    logger.info("✅ Бот запущен и работает!")
    logger.info("⏰ Напоминания настроены: 22:00 и 00:00")
    logger.info("🔍 Режим отладки включен")


if __name__ == "__main__":
    asyncio.run(main())